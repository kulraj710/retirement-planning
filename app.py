# app.py  –  FIRE planner (v2, June 2025)

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from scipy.optimize import brentq

# --------------------------------------------------
# 1. Sidebar – inputs
# --------------------------------------------------
st.sidebar.header("🔧  Assumptions & Targets")

today_year = date.today().year
curr_age   = st.sidebar.number_input("Current age", 18, 99, 24)

# <- removed future-salary inputs
curr_sal   = st.sidebar.number_input("Current annual salary (CAD)", 0.0, 1e9,
                                     45_000.0, step=1_000.0, format="%.0f")

sal_growth = st.sidebar.slider("Annual salary growth %", 0.0, 30.0, 3.0) / 100
save_rate  = st.sidebar.slider("Annual savings rate %", 0.0, 100.0, 25.0) / 100

curr_portf = st.sidebar.number_input("Current portfolio (CAD)", 0.0, 1e9,
                                     7_000.0, step=1_000.0, format="%.0f")

pre_ret    = st.sidebar.slider("Investment return before retirement %", 0.0, 30.0, 6.0) / 100
post_ret   = st.sidebar.slider("Return after retirement %",            0.0, 30.0, 5.0) / 100
infl       = st.sidebar.slider("Inflation %",                          0.0, 20.0, 2.0) / 100
swr        = st.sidebar.slider("Safe-withdrawal rate %",               2.0, 10.0, 4.0) / 100
tax        = st.sidebar.slider("Withdrawal tax drag %",                0.0, 50.0, 20.0) / 100

pension    = st.sidebar.number_input("CPP/OAS or other pension (today-$)", 0.0, 100_000.0,
                                     7_000.0, step=500.0, format="%.0f")

desire_sp  = st.sidebar.number_input("Desired annual spending (today-$)", 0.0, 1e7,
                                     10_000.0, step=1_000.0, format="%.0f")

# Target block for Goal-Seek
st.sidebar.markdown("---")
nest_target = st.sidebar.number_input("Nest-egg target (today-$)", 0.0, 1e9,
                                      5_000_000.0, step=100_000.0, format="%.0f")
age_target  = st.sidebar.number_input("Retirement age target", curr_age+1, 99, 35)
goal_var    = st.sidebar.selectbox("Solve for…", ["Savings rate",
                                                  "Salary growth",
                                                  "Pre-ret return"])

# --------------------------------------------------
# 2. Core projection
# --------------------------------------------------
def project(save_rate_=save_rate, sal_growth_=sal_growth, pre_ret_=pre_ret):
    years = np.arange(today_year, today_year + 80)
    age   = curr_age + (years - today_year)

    salary       = np.zeros_like(years, dtype=float)
    salary[0]    = curr_sal
    for i in range(1, len(salary)):
        salary[i] = salary[i-1] * (1 + sal_growth_)

    savings      = salary * save_rate_
    portf        = np.zeros_like(years, dtype=float)
    portf[0]     = curr_portf
    retired      = False
    first_yes_row = None

    real_portf   = np.zeros_like(years, dtype=float)
    real_wd      = np.zeros_like(years, dtype=float)
    can_retire   = np.array([""]*len(years), dtype=object)

    for i in range(len(years)):
        if i > 0:
            r = pre_ret_ if not retired else post_ret
            portf[i] = portf[i-1] + savings[i] + portf[i-1] * r

        real_portf[i]  = portf[i] / ((1 + infl) ** (years[i] - today_year))
        real_wd[i]     = real_portf[i] * swr * (1 - tax)
        real_pension   = pension if age[i] >= 65 else 0

        ok = (real_wd[i] + real_pension >= desire_sp) and (age[i] >= age_target)
        can_retire[i] = "YES" if ok else ""
        if ok and not retired:
            retired = True
            first_yes_row = i
            salary[i+1:]  = 0
            savings[i+1:] = 0

    df = pd.DataFrame({
        "Year": years,
        "Age": age,
        "Salary": salary,
        "Savings": savings,
        "Portfolio": portf,
        "Real Portfolio": real_portf,
        "Real Withdrawal": real_wd,
        "Can Retire?": can_retire
    })
    return df, first_yes_row

df, first_yes = project()

# --------------------------------------------------
# 3. Banner & metrics
# --------------------------------------------------
st.title("🏖️  FIRE / Retirement Planner")

if first_yes is not None:
    row = df.iloc[first_yes]
    banner = (f"### 🎉 You can retire in **{int(row['Year'])}** at "
              f"age **{int(row['Age'])}** with a real portfolio of "
              f"**CAD {row['Real Portfolio']:,.0f}**")
    st.markdown(banner)
    st.metric("Years until retirement", int(row['Age'] - curr_age))
    st.metric("Nominal portfolio at retirement", f"{row['Portfolio']:,.0f}")
else:
    st.warning("🔎 The portfolio never meets the criteria within 80 years.")

# --------------------------------------------------
# 4. Show table & charts
# --------------------------------------------------
st.subheader("Projection table (scrollable)")
fmt = {"Salary":"{:,.0f}",
       "Savings":"{:,.0f}",
       "Portfolio":"{:,.0f}",
       "Real Portfolio":"{:,.0f}",
       "Real Withdrawal":"{:,.0f}"}
st.dataframe(df.style.format(fmt), height=350)

st.subheader("Nominal portfolio vs. real withdrawal")
chart_df = df[["Year", "Portfolio", "Real Withdrawal"]].set_index("Year")
st.line_chart(chart_df)

st.subheader("Real portfolio (inflation-adjusted)")
st.line_chart(df.set_index("Year")["Real Portfolio"])

# --------------------------------------------------
# 5. Goal-Seek
# --------------------------------------------------
def gap_to_target(var):
    if goal_var == "Savings rate":
        df2,_ = project(save_rate_=var)
    elif goal_var == "Salary growth":
        df2,_ = project(sal_growth_=var)
    else:  # pre-ret return
        df2,_ = project(pre_ret_=var)
    real_bal = np.interp(age_target, df2["Age"], df2["Real Portfolio"])
    return real_bal - nest_target

if st.sidebar.button("Run Goal-Seek"):
    if goal_var == "Savings rate":
        low, high = 0.0, 1.0                       # 0–100 %
    elif goal_var == "Salary growth":
        low, high = 0.0, 0.50                      # 0–50 %
    else:
        low, high = 0.0, 0.30                      # 0–30 %
    try:
        sol = brentq(gap_to_target, low, high)
        if goal_var == "Savings rate":
            st.sidebar.success(f"Required savings-rate ≈ {sol*100:.2f} %")
        elif goal_var == "Salary growth":
            st.sidebar.success(f"Required salary growth ≈ {sol*100:.2f} %")
        else:
            st.sidebar.success(f"Required pre-ret return ≈ {sol*100:.2f} %")
    except ValueError:
        st.sidebar.error("❌ Target unaffordable even with extreme settings.")
