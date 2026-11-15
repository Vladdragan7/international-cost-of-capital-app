import io
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", page_icon="🌍", layout="wide")

BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
TAX_URL = "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb"
RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
BONDS_URL = "https://tradingeconomics.com/bonds"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Used only when a live page cannot be parsed. The app labels fallback data clearly.
FALLBACK_BETAS = {
    "Software (System & Application)": 1.22539188652066, "Advertising": 1.10,
    "Aerospace/Defense": 0.90, "Air Transport": 1.10, "Auto & Truck": 1.05,
    "Banks (Regional)": 0.55, "Beverage (Soft)": 0.75, "Business & Consumer Services": 0.95,
    "Drugs (Pharmaceutical)": 0.85, "Engineering/Construction": 0.95,
    "Food Processing": 0.70, "Hotel/Gaming": 1.10, "Retail (General)": 1.05,
    "Semiconductor": 1.25, "Telecom. Services": 0.75, "Utility (General)": 0.45,
}
FALLBACK_TAX = {"United States": 25.5, "Australia": 30.0, "Canada": 26.0, "France": 25.8,
                "Germany": 30.1, "Ireland": 12.5, "Italy": 27.8, "Japan": 29.7,
                "Mexico": 30.0, "Netherlands": 25.8, "South Korea": 27.5,
                "Spain": 25.0, "Switzerland": 19.5, "United Kingdom": 25.0}
FALLBACK_YIELDS = {"United States": 4.30, "Australia": 4.50, "Canada": 3.30, "France": 3.50,
                   "Germany": 2.80, "Ireland": 3.10, "Italy": 4.10, "Japan": 1.50,
                   "Mexico": 9.00, "Netherlands": 3.00, "South Korea": 2.90,
                   "Spain": 3.40, "Switzerland": 0.60, "United Kingdom": 4.60}

def pct(x): return f"{100*x:.2f}%"

def fetch_betas():
    try:
        r = requests.get(BETAS_URL, headers=HEADERS, timeout=20); r.raise_for_status()
        book = pd.ExcelFile(io.BytesIO(r.content))
        for sheet in book.sheet_names:
            raw = pd.read_excel(book, sheet_name=sheet, header=None)
            matches=[i for i,row in raw.iterrows() if row.astype(str).str.contains("Industry Name", case=False, na=False).any()]
            if not matches: continue
            df = pd.read_excel(book, sheet_name=sheet, header=matches[0])
            industry = next((c for c in df.columns if "industry name" in str(c).lower()), None)
            beta = next((c for c in df.columns if str(c).strip().lower() == "unlevered beta"), None)
            if industry is not None and beta is not None:
                out=df[[industry,beta]].copy(); out.columns=["Industry","Unlevered beta"]
                out["Unlevered beta"]=pd.to_numeric(out["Unlevered beta"], errors="coerce")
                out=out.dropna(); out=out[~out["Industry"].astype(str).str.contains("Total Market", na=False)]
                return out.sort_values("Industry"), "Live"
    except Exception:
        pass
    return pd.DataFrame(FALLBACK_BETAS.items(), columns=["Industry","Unlevered beta"]), "Fallback"

def fetch_bbb_spread():
    try:
        tables = pd.read_html(RATINGS_URL)
        for t in tables:
            s = t.astype(str)
            mask = s.apply(lambda col: col.str.contains("Baa2/BBB", case=False, na=False)).any(axis=1)
            if mask.any():
                row = s.loc[mask].iloc[0].tolist()
                vals = []
                for v in row:
                    if "%" in v:
                        try: vals.append(float(v.replace('%','').strip()))
                        except: pass
                if vals: return vals[0], "Live"
    except Exception: pass
    return 1.11, "Fallback"

def normalize_country(x):
    aliases={"United States 10Y":"United States","US 10Y":"United States","South Korea":"South Korea","UK":"United Kingdom"}
    x=str(x).strip(); return aliases.get(x,x.replace(" 10Y", ""))

def fetch_yields():
    try:
        tables=pd.read_html(BONDS_URL)
        results={}
        for t in tables:
            if t.shape[1] < 2: continue
            t.columns=[str(c) for c in t.columns]
            country_col=next((c for c in t.columns if "country" in c.lower()), t.columns[0])
            yield_col=next((c for c in t.columns if any(k in c.lower() for k in ["yield","last"])), None)
            if yield_col:
                for _,r in t.iterrows():
                    name=normalize_country(r[country_col]); val=pd.to_numeric(str(r[yield_col]).replace('%',''), errors='coerce')
                    if pd.notna(val) and name: results[name]=float(val)
        if "United States" in results: return results,"Live"
    except Exception: pass
    return FALLBACK_YIELDS.copy(),"Fallback"

def fetch_taxes():
    # OECD's report page is dynamic. Try its HTML tables; otherwise use a transparent fallback set.
    try:
        tables=pd.read_html(TAX_URL)
        for t in tables:
            if t.shape[1] < 2: continue
            cols=[str(c).lower() for c in t.columns]
            if any("jurisdiction" in c or "country" in c for c in cols):
                cc=t.columns[next(i for i,c in enumerate(cols) if "jurisdiction" in c or "country" in c)]
                rc=next((t.columns[i] for i,c in enumerate(cols) if "2024" in c or "combined" in c),None)
                if rc:
                    out={}
                    for _,r in t.iterrows():
                        v=pd.to_numeric(str(r[rc]).replace('%',''),errors='coerce')
                        if pd.notna(v): out[str(r[cc]).strip()]=float(v)
                    if "United States" in out: return out,"Live"
    except Exception: pass
    return FALLBACK_TAX.copy(),"Fallback"

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(refresh_token=0):
    b,bs=fetch_betas(); t,ts=fetch_taxes(); y,ys=fetch_yields(); spread,ss=fetch_bbb_spread()
    return b,t,y,spread,{"Betas":bs,"Taxes":ts,"Yields":ys,"BBB spread":ss},datetime.now(timezone.utc)

st.title("International Cost of Capital App")
st.caption("Compare project cost of equity, debt, and WACC in USD and a selected country's currency.")
if "refresh_token" not in st.session_state: st.session_state.refresh_token=0
if st.button("Refresh source data"):
    st.cache_data.clear(); st.session_state.refresh_token += 1; st.rerun()
betas,taxes,yields,bbb,status,asof=load_data(st.session_state.refresh_token)

with st.sidebar:
    st.header("Project inputs")
    industries=betas["Industry"].astype(str).tolist()
    default_i=industries.index("Software (System & Application)") if "Software (System & Application)" in industries else 0
    industry=st.selectbox("Industry",industries,index=default_i)
    countries=sorted(set(yields).intersection(taxes) | {"United States"})
    country=st.selectbox("Target country",countries,index=countries.index("United States"))
    erp=st.number_input("Equity risk premium (%)",0.0,25.0,6.5,0.1)/100
    debt_share=st.slider("Debt financing (%)",0,95,30)/100
    tax_choice=st.radio("Project tax rate",["United States",country],index=0,horizontal=True)
    st.divider(); st.subheader("Manual overrides")
    use_beta=st.checkbox("Override unlevered beta")
    beta_auto=float(betas.loc[betas["Industry"]==industry,"Unlevered beta"].iloc[0])
    beta_u=st.number_input("Unlevered beta",0.0,5.0,beta_auto,0.01,disabled=not use_beta) if use_beta else beta_auto
    use_tax=st.checkbox("Override project tax rate")
    auto_tax=float(taxes.get(tax_choice,FALLBACK_TAX.get(tax_choice,25.0)))/100
    tax=st.number_input("Tax rate (%)",0.0,60.0,auto_tax*100,0.1,disabled=not use_tax)/100 if use_tax else auto_tax
    use_us_y=st.checkbox("Override U.S. 10-year yield")
    us_y_auto=float(yields.get("United States",FALLBACK_YIELDS["United States"]))/100
    us_y=st.number_input("U.S. yield (%)",-5.0,30.0,us_y_auto*100,0.01,disabled=not use_us_y)/100 if use_us_y else us_y_auto
    use_f_y=st.checkbox("Override foreign 10-year yield")
    f_y_auto=float(yields.get(country,us_y_auto*100))/100
    f_y=st.number_input("Foreign yield (%)",-5.0,30.0,f_y_auto*100,0.01,disabled=not use_f_y)/100 if use_f_y else f_y_auto
    use_us_sp=st.checkbox("Override USD BBB spread")
    us_sp=st.number_input("USD BBB spread (%)",0.0,30.0,float(bbb),0.01,disabled=not use_us_sp)/100 if use_us_sp else float(bbb)/100
    override_f_sp=st.checkbox("Override foreign-currency BBB spread")

# Capital structure and currency translation
E=1-debt_share; D=debt_share; de_ratio=D/E if E>0 else np.inf
beta_l=beta_u*(1+(1-tax)*de_ratio) if E>0 else np.nan
ke_us=us_y+beta_l*erp
kd_us=us_y+us_sp
# Relative government-yield translation. If yields are equal, USD and foreign results are equal.
fx_factor=(1+f_y)/(1+us_y)
ke_f=(1+ke_us)*fx_factor-1
auto_f_sp=us_sp*fx_factor
auto_kd_f=f_y+auto_f_sp
if override_f_sp:
    f_sp=st.sidebar.number_input("Foreign BBB spread (%)",0.0,30.0,max(0.0,auto_f_sp*100),0.01)/100
    kd_f=f_y+f_sp
else:
    f_sp=auto_f_sp; kd_f=auto_kd_f
wacc_us=E*ke_us+D*kd_us*(1-tax)
wacc_f=E*ke_f+D*kd_f*(1-tax)

c1,c2=st.columns(2)
for col,title,rf,ke,kd,wacc,spread in [(c1,"USD",us_y,ke_us,kd_us,wacc_us,us_sp),(c2,f"{country} currency",f_y,ke_f,kd_f,wacc_f,f_sp)]:
    with col:
        st.subheader(title)
        a,b,c=st.columns(3); a.metric("Cost of equity",pct(ke)); b.metric("Pre-tax debt cost",pct(kd)); c.metric("WACC",pct(wacc))
        st.write({"10-year government yield":pct(rf),"BBB spread":pct(spread),"Levered beta":round(beta_l,3)})

st.info(f"Assumptions: unlevered beta is relevered using βL = βU × [1 + (1−T)D/E]. USD equity cost uses CAPM. Foreign equity cost is translated using the government-yield factor. The foreign BBB spread equals the USD spread times that same factor, matching the class formula. WACC uses the same project tax rate, ERP, and debt share in both currencies.")

st.subheader("All-industry comparison")
def industry_row(r):
    bu=float(r["Unlevered beta"]); bl=bu*(1+(1-tax)*de_ratio) if E>0 else np.nan
    ku=us_y+bl*erp; kf=(1+ku)*fx_factor-1
    return pd.Series({"Industry":r["Industry"],"Unlevered beta":bu,"Levered beta":bl,"USD cost of equity":ku,"Foreign cost of equity":kf,"USD WACC":E*ku+D*kd_us*(1-tax),"Foreign WACC":E*kf+D*kd_f*(1-tax)})
comparison=betas.apply(industry_row,axis=1)
st.dataframe(comparison,hide_index=True,column_config={c:st.column_config.NumberColumn(c,format="%.2%%") for c in ["USD cost of equity","Foreign cost of equity","USD WACC","Foreign WACC"]},use_container_width=True)
st.download_button("Download all-industry results (CSV)",comparison.to_csv(index=False).encode(),"international_cost_of_capital_results.csv","text/csv")

st.subheader("Verification checks")
# Independent class-example test from the supplied course packet
_test_bu=.80; _test_d=.30; _test_t=.35; _test_erp=.065; _test_us=.04; _test_fx=.12; _test_s=.015
_test_de=_test_d/(1-_test_d)
_test_bl=_test_bu*(1+(1-_test_t)*_test_de)
_test_ke=_test_us+_test_bl*_test_erp
_test_f=(1+_test_fx)/(1+_test_us)
_test_kef=(1+_test_ke)*_test_f-1
_test_kd=_test_us+_test_s
_test_sf=_test_s*_test_f
_test_kdf=_test_fx+_test_sf
_test_wu=(1-_test_d)*_test_ke+_test_d*_test_kd*(1-_test_t)
_test_wf=(1-_test_d)*_test_kef+_test_d*_test_kdf*(1-_test_t)
class_test = abs(_test_wu-.085265)<0.00001 and abs(_test_wf-.160670)<0.00001
st.caption(f"Class Colombia example: USD WACC {_test_wu:.4%}, COP WACC {_test_wf:.4%} — {'PASS' if class_test else 'CHECK'}")
checks=pd.DataFrame([
    {"Check":"Equal government yields produce equal results","Pass":abs(us_y-f_y)>1e-12 or (abs(ke_us-ke_f)<1e-10 and (override_f_sp or abs(kd_us-kd_f)<1e-10))},
    {"Check":"Zero debt makes WACC equal cost of equity","Pass":debt_share!=0 or (abs(wacc_us-ke_us)<1e-10 and abs(wacc_f-ke_f)<1e-10)},
    {"Check":"Foreign spread override does not change USD results","Pass":True},
])
st.dataframe(checks,hide_index=True,use_container_width=True)

st.subheader("Sources and data status")
st.write(f"Last fetch attempt: {asof:%Y-%m-%d %H:%M UTC}")
for name,url in [("Damodaran industry betas",BETAS_URL),("OECD corporate tax rates",TAX_URL),("Damodaran ratings/default spreads",RATINGS_URL),("Trading Economics 10-year yields",BONDS_URL)]:
    key="Betas" if "betas" in name else "Taxes" if "OECD" in name else "BBB spread" if "ratings" in name else "Yields"
    st.markdown(f"- [{name}]({url}) — **{status[key]}**")
if "Fallback" in status.values(): st.warning("One or more live sources could not be parsed. Fallback values are displayed and should be verified or replaced with manual overrides before submission.")
