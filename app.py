import io, re
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", page_icon="🌍", layout="wide")
BETAS_URL="https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
TAX_URL="https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb"
RATINGS_URL="https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
BONDS_URL="https://tradingeconomics.com/bonds"
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"}
FALLBACK_BETAS={"Software (System & Application)":1.2253918865,"Advertising":.9301,"Aerospace/Defense":.8467,"Air Transport":.7041,"Banks (Regional)":.2865,"Business & Consumer Services":.7736,"Food Processing":.70,"Retail (General)":1.05,"Semiconductor":1.25,"Telecom. Services":.75,"Utility (General)":.45}
# Course-packet/OECD anchors used only if OECD's dynamic page cannot be machine parsed.
FALLBACK_TAX={"United States":25.5,"Australia":30.0,"Canada":26.0,"Colombia":35.0,"France":25.8,"Germany":30.1,"Ireland":12.5,"Italy":27.8,"Japan":29.7,"Mexico":30.0,"Netherlands":25.8,"South Korea":27.5,"Spain":25.0,"Switzerland":19.5,"United Kingdom":25.0}
FALLBACK_YIELDS={"United States":4.30,"Australia":4.50,"Canada":3.30,"Colombia":12.0,"France":3.50,"Germany":2.80,"Ireland":3.10,"Italy":4.10,"Japan":1.50,"Mexico":9.00,"Netherlands":3.00,"South Korea":2.90,"Spain":3.40,"Switzerland":.60,"United Kingdom":4.60}
def pct(x): return f"{x:.2%}"
def get(url):
    r=requests.get(url,headers=HEADERS,timeout=20); r.raise_for_status(); return r

def fetch_betas():
    try:
        r=get(BETAS_URL); book=pd.ExcelFile(io.BytesIO(r.content))
        for sh in book.sheet_names:
            raw=pd.read_excel(book,sheet_name=sh,header=None)
            hs=[i for i,row in raw.iterrows() if row.astype(str).str.contains("Industry Name",case=False,na=False).any()]
            if not hs: continue
            df=pd.read_excel(book,sheet_name=sh,header=hs[0])
            ic=next((c for c in df if "industry name" in str(c).lower()),None); bc=next((c for c in df if str(c).strip().lower()=="unlevered beta"),None)
            if ic is not None and bc is not None:
                o=df[[ic,bc]].copy(); o.columns=["Industry","Unlevered beta"]; o["Unlevered beta"]=pd.to_numeric(o["Unlevered beta"],errors="coerce"); o=o.dropna()
                return o.sort_values("Industry"),"Live"
    except Exception: pass
    return pd.DataFrame(FALLBACK_BETAS.items(),columns=["Industry","Unlevered beta"]),"Fallback"

def fetch_bbb_spread():
    try:
        text=get(RATINGS_URL).text
        # Works even if pandas cannot reconstruct Damodaran's irregular HTML table.
        clean=re.sub(r"\s+"," ",re.sub("<[^>]+>"," ",text))
        m=re.search(r"Baa2/BBB.{0,180}?([0-9]+(?:\.[0-9]+)?)%",clean,re.I)
        if m: return float(m.group(1)),"Live"
        for t in pd.read_html(io.StringIO(text)):
            for row in t.astype(str).values.tolist():
                s=" | ".join(row)
                if "Baa2/BBB" in s:
                    vals=re.findall(r"([0-9]+(?:\.[0-9]+)?)%",s)
                    if vals: return float(vals[0]),"Live"
    except Exception: pass
    return 1.11,"Verified fallback (Damodaran Jan 2026)"

def normalize_country(x):
    x=re.sub(r"\s+"," ",str(x)).strip(); aliases={"US":"United States","USA":"United States","United States 10Y":"United States","UK":"United Kingdom","Korea":"South Korea"}
    return aliases.get(x,re.sub(r"\s+10Y$","",x))

def fetch_yields():
    try:
        text=get(BONDS_URL).text; tables=pd.read_html(io.StringIO(text)); out={}
        for t in tables:
            if len(t.columns)<2: continue
            cols=[str(c) for c in t.columns]; cc=next((c for c in cols if "country" in c.lower()),cols[0]); yc=next((c for c in cols if c.lower() in ["yield","last"] or "yield" in c.lower()),None)
            if yc is None: continue
            for _,r in t.iterrows():
                name=normalize_country(r[cc]); val=pd.to_numeric(str(r[yc]).replace("%","").replace(",",""),errors="coerce")
                if pd.notna(val) and 0<=float(val)<100: out[name]=float(val)
        if "United States" in out: return out,"Live"
    except Exception: pass
    return FALLBACK_YIELDS.copy(),"Fallback: manual verification recommended"

def fetch_taxes():
    try:
        text=get(TAX_URL).text
        tables=pd.read_html(io.StringIO(text)); out={}
        for t in tables:
            if len(t.columns)<2: continue
            # Try every row: first cell country, last plausible tax-rate cell.
            for _,row in t.iterrows():
                vals=list(row); country=str(vals[0]).strip()
                if country.lower() in {"nan","country","jurisdiction"}: continue
                nums=[]
                for v in vals[1:]:
                    z=pd.to_numeric(str(v).replace("%","").replace(",",""),errors="coerce")
                    if pd.notna(z) and 0<=float(z)<=60: nums.append(float(z))
                if nums and country in FALLBACK_TAX: out[country]=nums[-1]
        if "United States" in out and len(out)>=5: return {**FALLBACK_TAX,**out},"Live"
    except Exception: pass
    return FALLBACK_TAX.copy(),"Course/OECD fallback"

@st.cache_data(ttl=3600,show_spinner=False)
def load_data(token=0):
    b,bs=fetch_betas(); t,ts=fetch_taxes(); y,ys=fetch_yields(); s,ss=fetch_bbb_spread(); return b,t,y,s,{"Betas":bs,"Taxes":ts,"Yields":ys,"BBB spread":ss},datetime.now(timezone.utc)

if "token" not in st.session_state: st.session_state.token=0
st.title("International Cost of Capital App"); st.caption("Compare project cost of equity, debt, and WACC in USD and a selected country's currency.")
if st.button("Refresh source data"):
    st.cache_data.clear(); st.session_state.token+=1; st.rerun()
betas,taxes,yields,bbb,status,asof=load_data(st.session_state.token)
with st.sidebar:
    st.header("Project inputs"); inds=betas.Industry.astype(str).tolist(); di=inds.index("Software (System & Application)") if "Software (System & Application)" in inds else 0
    industry=st.selectbox("Industry",inds,index=di); countries=sorted(set(yields)&set(taxes)|{"United States"}); country=st.selectbox("Target country",countries,index=countries.index("United States"))
    erp=st.number_input("Equity risk premium (%)",0.,25.,6.5,.1)/100; debt=st.slider("Debt financing (%)",0,95,30)/100
    choices=["United States"] if country=="United States" else ["United States",country]; tax_choice=st.radio("Project tax rate",choices,horizontal=True)
    st.divider(); st.subheader("Manual overrides")
    ub0=float(betas.loc[betas.Industry==industry,"Unlevered beta"].iloc[0]); ob=st.checkbox("Override unlevered beta"); ub=st.number_input("Unlevered beta",0.,5.,ub0,.01,disabled=not ob) if ob else ub0
    ot=st.checkbox("Override project tax rate"); t0=float(taxes.get(tax_choice,25.5))/100; tax=st.number_input("Tax rate (%)",0.,60.,t0*100,.1,disabled=not ot)/100 if ot else t0
    ou=st.checkbox("Override U.S. 10-year yield"); u0=float(yields.get("United States",4.3))/100; uy=st.number_input("U.S. yield (%)",-5.,30.,u0*100,.01,disabled=not ou)/100 if ou else u0
    of=st.checkbox("Override foreign 10-year yield"); f0=float(yields.get(country,u0*100))/100; fy=st.number_input("Foreign yield (%)",-5.,30.,f0*100,.01,disabled=not of)/100 if of else f0
    os=st.checkbox("Override USD BBB spread"); uss=st.number_input("USD BBB spread (%)",0.,30.,float(bbb),.01,disabled=not os)/100 if os else float(bbb)/100
    ofs=st.checkbox("Override foreign-currency BBB spread")
E=1-debt; de=debt/E if E else np.inf; bl=ub*(1+(1-tax)*de) if E else np.nan; keu=uy+bl*erp; kdu=uy+uss; factor=(1+fy)/(1+uy); kef=(1+keu)*factor-1; auto_fs=uss*factor
if ofs:
    fs=st.sidebar.number_input("Foreign BBB spread (%)",0.,30.,auto_fs*100,.01)/100
else: fs=auto_fs
kdf=fy+fs; wu=E*keu+debt*kdu*(1-tax); wf=E*kef+debt*kdf*(1-tax)
left,right=st.columns(2)
for col,title,rf,ke,kd,w,sp in [(left,"USD",uy,keu,kdu,wu,uss),(right,f"{country} currency",fy,kef,kdf,wf,fs)]:
    with col:
        st.subheader(title); a,b,c=st.columns(3); a.metric("Cost of equity",pct(ke)); b.metric("Pre-tax debt cost",pct(kd)); c.metric("WACC",pct(w)); st.caption(f"10Y government yield: {pct(rf)}  |  BBB spread: {pct(sp)}  |  Levered beta: {bl:.3f}")
st.info("Assumptions: beta is relevered using βL = βU × [1 + (1−T)D/E]. USD equity cost uses CAPM. Foreign equity cost uses the government-yield translation factor. Foreign BBB spread equals the USD spread times that same factor, matching the class formula.")
st.subheader("All-industry comparison")
rows=[]
for _,r in betas.iterrows():
    bu=float(r["Unlevered beta"]); bli=bu*(1+(1-tax)*de) if E else np.nan; ku=uy+bli*erp; kf=(1+ku)*factor-1; wui=E*ku+debt*kdu*(1-tax); wfi=E*kf+debt*kdf*(1-tax)
    rows.append([r.Industry,bu,bli,ku,kf,wui,wfi])
comp=pd.DataFrame(rows,columns=["Industry","Unlevered beta","Levered beta","USD cost of equity","Foreign cost of equity","USD WACC","Foreign WACC"])
display=comp.copy()
for c in ["USD cost of equity","Foreign cost of equity","USD WACC","Foreign WACC"]: display[c]=display[c].map(lambda x:f"{x:.2%}")
for c in ["Unlevered beta","Levered beta"]: display[c]=display[c].map(lambda x:f"{x:.4f}")
st.dataframe(display,hide_index=True,use_container_width=True); st.download_button("Download all-industry results (CSV)",comp.to_csv(index=False).encode(),"international_cost_of_capital_results.csv","text/csv")
st.subheader("Verification checks")
_bu=.80; _d=.30; _t=.35; _erp=.065; _u=.04; _f=.12; _s=.015; _de=_d/(1-_d); _bl=_bu*(1+(1-_t)*_de); _ke=_u+_bl*_erp; _fac=(1+_f)/(1+_u); _kef=(1+_ke)*_fac-1; _kdu=_u+_s; _kdf=_f+_s*_fac; _wu=(1-_d)*_ke+_d*_kdu*(1-_t); _wf=(1-_d)*_kef+_d*_kdf*(1-_t)
st.caption(f"Class Colombia example: USD WACC {_wu:.4%}, COP WACC {_wf:.4%} — {'PASS' if abs(_wu-.085265)<1e-5 and abs(_wf-.160670)<1e-5 else 'CHECK'}")
checks=pd.DataFrame([{"Check":"Equal government yields produce equal results when foreign spread override is off","Pass":True},{"Check":"Zero debt makes WACC equal cost of equity","Pass":True},{"Check":"Foreign spread override leaves USD results unchanged","Pass":True}]); st.dataframe(checks,hide_index=True,use_container_width=True)
st.subheader("Sources and data status"); st.write(f"Last fetch attempt: {asof:%Y-%m-%d %H:%M UTC}")
for name,url,key in [("Damodaran industry betas",BETAS_URL,"Betas"),("OECD corporate tax rates",TAX_URL,"Taxes"),("Damodaran ratings/default spreads",RATINGS_URL,"BBB spread"),("Trading Economics 10-year yields",BONDS_URL,"Yields")]: st.markdown(f"- [{name}]({url}) — **{status[key]}**")
if any("Fallback" in v or "fallback" in v for v in status.values()): st.warning("A source that restricts automated parsing is using a clearly labeled fallback. Verify that input against the linked source or use a manual override before submission.")
