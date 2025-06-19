# app.py  –  FIRE/Retirement Planner with Guided UI  (June 2025)

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from scipy.optimize import brentq

# ---------- 0. Page config ----------
st.set_page_config(page_title="FIRE Planner", page_icon="🏖️")

# ---------- 1. Title & Quick-Start ----------
st.title("🏖️  FIRE / Retirement Planner")

with st.expander("📖 Quick Start – How do I use this?", expanded=True):
    st.markdown("""
    1. **Enter today’s numbers** in the sidebar (age, salary, portfolio).  
    2. **Tweak the sliders** for savings-rate, investment return, etc.  
    3. Watch the banner update – green ✅ means the plan reaches your spending goal.  
    4. **Goal-Seek** box → pick a variable, set an age & nest-egg target, click *Run*.  
       The app tells you *“required savings-rate 42 %”* (or salary-growth, or return).  
    5. Scroll the table & charts to see the year-by-year cash-flow details.  
    """)

# ---------- 2. Sidebar – Inputs with tool tips ----------
st.sidebar.header("🔧  Assumptions")

today_year = date.today().year

curr_age = st.sidebar.number_input(
    "Current age (years)",
    min_value=18, max_value=99, value=24,
    help="Your age today. Used to build the timeline."
)

curr_sal = st.sidebar.number_input(
    "Current annual salary (CAD)",
    0.0, 1e9, 45_000.0, step=1_000.0, format="%.0f",
    help="Before-tax pay this year. Grows by the % slider below."
)

sal_growth = st.sidebar.slider(
    "Annual salary growth (%)",
    0.0, 30.0, 3.0, help="Average yearly raise. 3 % ≈ inflation-plus-merit."
) / 100

save_rate = st.sidebar.slider(
    "Savings rate (% of salary)",
    0.0, 100.0, 25.0,
    help="Portion of gross salary you invest every year."
) / 100

curr_portf = st.sidebar.number_input(
    "Current portfolio (CAD)",
    0.0, 1e9, 7_000.0, step=1_000.0, format="%.0f",
    help="Total invested assets today (RRSP, TFSA, brokerage, crypto…)."
)

pre_ret = st.sidebar.slider(
    "Investment return **before** retirement (%)",
    0.0, 30.0, 6.0,
    help="Expected average annual growth of the portfolio while you’re working."
) / 100

post_ret = st.sidebar.slider(
    "Return **after** retirement (%)",
    0.0, 30.0, 5.0,
    help="Usually lower because you hold more bonds or cash."
) / 100

infl = st.sidebar.slider(
    "Inflation (%)",
    0.0, 20.0, 2.0,
    help="Used to convert all results to **today’s dollars**."
) / 100

swr = st.sidebar.slider(
    "Safe-withdrawal rate (%)",
    2.0, 10.0, 4.0,
    help="Classic 4 % rule: first-year withdrawal = 4 % of portfolio, then adjust for inflation."
) / 100

tax = st.sidebar.slider(
    "Tax drag on withdrawals (%)",
    0.0, 50.0, 20.0,
    help="Flat percentage lost to income tax / fees when you spend the money."
) / 100

pension = st.sidebar.number_input(
    "CPP / OAS or other pension (today-$)",
    0.0, 100_000.0, 7_000.0, step=500.0, format="%.0f",
    help="Annual pension income starting at age 65, already in today’s dollars."
)

desire_sp = st.sidebar.number_input(
    "Desired annual spending (today-$)",
    0.0, 1e7, 10_000.0, step=1_000.0, format="%.0f",
    help="How much you want to spend each year **after** tax in retirement, in today’s dollars."
)

# ---------- 3. Goal-Seek block ----------
st.sidebar.markdown("---")
st.sidebar.subheader("🎯  Goal-Seek")

nest_target = st.sidebar.number_input(
    "Nest-egg target (today-$)",
    0.0, 1e9, 5_000_000.0, step=100_000.0, format="%.0f",
    help="Portfolio size (real dollars) you want by the chosen age."
)
age_target = st.sidebar.number_input(
    "Target retirement age",
    curr_age + 1, 99, 35,
    help="Age at which the Goal-Seek tries to hit the nest-egg above."
)
goal_var = st.sidebar.selectbox(
    "Solve for this variable",
    ["Savings rate", "Salary growth", "Pre-ret return"],
    help="Which dial should the optimiser turn to hit the target?"
)

# ---------- 4. Core projection function ----------
def project(save_rate_=save_rate, sal_growth_=sal_growth, pre_ret_=pre_ret):
    years = np.arange(today_year, today_year + 80)
    age   = curr_age + years - today_year

    salary = np.zeros_like(years, dtype=float)
    salary[0] = curr_sal
    for i in range(1, len(salary)):
        salary[i] = salary[i-1]*(1 + sal_growth_)

    savings = salary * save_rate_
    portf   = np.zeros_like(years, dtype=float)
    portf[0] = curr_portf

    retired = False
    first_yes = None
    real_portf = np.zeros_like(years, dtype=float)
    real_wd    = np.zeros_like(years, dtype=float)
    can_retire = np.array([""]*len(years), dtype=object)

    for i in range(len(years)):
        if i > 0:
            growth_rate = pre_ret_ if not retired else post_ret
            portf[i] = portf[i-1] + savings[i] + portf[i-1]*growth_rate

        real_portf[i] = portf[i] / ((1+infl)**(years[i] - today_year))
        real_wd[i]    = real_portf[i]*swr*(1 - tax)
        real_pen      = pension if age[i] >= 65 else 0

        if (real_wd[i] + real_pen >= desire_sp) and (age[i] >= curr_age):
            can_retire[i] = "YES"
            if not retired:
                retired = True
                first_yes = i
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
    return df, first_yes

df, first_yes = project()

# ---------- 5. Banner & metrics ----------
if first_yes is not None:
    r = df.iloc[first_yes]
    st.success(f"### ✅  Retire in **{int(r.Year)}** at age **{int(r.Age)}**  "
               f"with **real portfolio CAD {r['Real Portfolio']:,.0f}**")
    st.metric("Years until retirement", int(r.Age - curr_age))
    st.metric("Nominal portfolio at retirement", f"{r.Portfolio:,.0f}")
else:
    st.warning("🚧  Goal not reached within 80 years. Adjust inputs or use Goal-Seek.")

# ---------- 6. Tables & charts ----------
st.subheader("Projection table")
fmt = {"Salary":"{:,.0f}", "Savings":"{:,.0f}",
       "Portfolio":"{:,.0f}", "Real Portfolio":"{:,.0f}",
       "Real Withdrawal":"{:,.0f}"}
st.dataframe(df.style.format(fmt), height=350)

st.subheader("Portfolio vs. real withdrawal stream")
st.line_chart(df.set_index("Year")[["Portfolio", "Real Withdrawal"]])

st.subheader("Inflation-adjusted (real) portfolio")
st.line_chart(df.set_index("Year")["Real Portfolio"])

# ---------- 7. Goal-Seek (root-finder) ----------
def gap_to_target(var):
    if goal_var == "Savings rate":
        df2, _ = project(save_rate_=var)
    elif goal_var == "Salary growth":
        df2, _ = project(sal_growth_=var)
    else:  # pre-ret return
        df2, _ = project(pre_ret_=var)
    real_bal = np.interp(age_target, df2["Age"], df2["Real Portfolio"])
    return real_bal - nest_target

if st.sidebar.button("Run Goal-Seek"):
    bounds = {"Savings rate": (0.0, 1.0),
              "Salary growth": (0.0, 0.50),
              "Pre-ret return": (0.0, 0.30)}
    low, high = bounds[goal_var]
    try:
        sol = brentq(gap_to_target, low, high)
        label = {"Savings rate": "%", "Salary growth": "%", "Pre-ret return": "%"}[goal_var]
        st.sidebar.success(f"Required {goal_var.lower()} ≈ {sol*100:.2f}{label}")
    except ValueError:
        st.sidebar.error("❌  Target unreachable even at extreme settings.")

# ---------- 8. Footer ----------
st.markdown("---")
st.caption("This tool is for **educational planning only** and does not constitute financial advice. "
           "Consider taxes, fees, and personal risk tolerance before making decisions.")
