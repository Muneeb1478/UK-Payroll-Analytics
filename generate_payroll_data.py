"""Synthetic UK payroll dataset generator (2026/27 tax year, Apr 2026 - Mar 2027).
ALL DATA IS FAKE. Verify rates on GOV.UK/HMRC before publishing."""
import numpy as np, pandas as pd, random, string
rng = np.random.default_rng(42); random.seed(42)

N = 300
MONTHS = pd.period_range("2026-04", "2027-03", freq="M")

# --- Rates (verify on GOV.UK) ---
NMW = {"21+": 12.71, "18-20": 10.85, "Under18/App": 8.00}
PA, BASIC_LIM, HIGHER_LIM = 12570, 50270, 125140
NI_PT_M, NI_UEL_M = 1048, 4189          # employee NI monthly thresholds
ER_NI_ST_M, ER_NI_RATE = 417, 0.15      # employer NI
PEN_LOW, PEN_HIGH = 6240, 50270         # qualifying earnings band
SL_PLAN2_M = 29385 / 12                 # student loan plan 2 monthly threshold

first = ["Oliver","Amelia","Noah","Isla","Muhammad","Fatima","Ali","Aisha","James","Emily","Callum","Fiona","Ewan","Morag","Liam","Sophie","Hamza","Zainab","Ryan","Kirsty","Jack","Eilidh","Ahmed","Maryam","Lewis","Rosie"]
last  = ["Smith","Brown","Wilson","Campbell","Stewart","Khan","Ahmed","Reid","Murray","Scott","Anderson","Clark","Hussain","MacDonald","Thomson","Robertson","Ali","Young","Mitchell","Watson"]
depts = {"Operations":(24000,34000),"Finance":(30000,52000),"HR":(28000,45000),"IT":(36000,70000),
         "Sales":(24000,48000),"Customer Service":(22000,30000),"Warehouse":(22000,29000)}
dept_names = list(depts); dept_w = [.22,.1,.07,.12,.15,.2,.14]

def ni_number():
    l = lambda: random.choice("ABCEGHJKLMNPRSTWXYZ")
    return f"{l()}{l()}{random.randint(100000,999999)}{random.choice('ABCD')}"

rows = []
for i in range(1, N+1):
    d = rng.choice(dept_names, p=dept_w); lo, hi = depts[d]
    age = int(rng.integers(17, 63))
    band = "Under18/App" if age < 18 else "18-20" if age < 21 else "21+"
    full = rng.random() > 0.2
    hrs_week = 37.5 if full else float(rng.choice([16,20,24,30]))
    if full:
        sal = float(round(rng.uniform(lo, hi), -2))
        rate = round(sal / (hrs_week*52), 2)
    else:
        rate = round(max(NMW[band], rng.uniform(NMW[band], NMW[band]+4)), 2)
        sal = round(rate*hrs_week*52, 2)
    if rate < NMW[band]:   # keep baseline compliant
        rate = NMW[band]; sal = round(rate*hrs_week*52, 2)
    start = pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(rng.integers(0, 3000)))
    rows.append(dict(
        employee_id=f"E{i:04d}", name=f"{random.choice(first)} {random.choice(last)}",
        ni_number=ni_number(), department=d, age=age, nmw_band=band,
        contract_hours_week=hrs_week, hourly_rate=rate, annual_salary=sal,
        tax_code="1257L", pension_optin=bool(rng.random() > 0.12),
        student_loan_plan2=bool(rng.random() < 0.15),
        bank_account=f"{rng.integers(10000000,99999999)}", start_date=start.date()))
emp = pd.DataFrame(rows)

def paye_month(taxable_annual):
    t = max(0, taxable_annual - PA)
    tax = 0.2*min(t, BASIC_LIM-PA) + 0.4*max(0, min(t, HIGHER_LIM-PA) - (BASIC_LIM-PA))
    return tax/12

recs = []
for _, e in emp.iterrows():
    for m in MONTHS:
        base = e.annual_salary/12
        ot_hrs = max(0, round(rng.normal(4, 3), 1)) if e.department in ("Warehouse","Operations","Customer Service") else max(0, round(rng.normal(1, 1.5), 1))
        ot_pay = round(ot_hrs * e.hourly_rate * 1.5, 2)
        gross = round(base + ot_pay, 2)
        pen_base = max(0, min(gross*12, PEN_HIGH) - PEN_LOW)/12
        ee_pen = round(0.05*pen_base, 2) if e.pension_optin else 0.0
        er_pen = round(0.03*pen_base, 2) if e.pension_optin else 0.0
        tax = round(paye_month((gross - ee_pen)*12), 2)
        ni = round(0.08*max(0, min(gross, NI_UEL_M)-NI_PT_M) + 0.02*max(0, gross-NI_UEL_M), 2)
        er_ni = round(ER_NI_RATE*max(0, gross-ER_NI_ST_M), 2)
        sl = round(0.09*max(0, gross-SL_PLAN2_M), 2) if e.student_loan_plan2 else 0.0
        net = round(gross - tax - ni - ee_pen - sl, 2)
        recs.append(dict(pay_month=str(m), employee_id=e.employee_id, department=e.department,
            ni_number=e.ni_number, bank_account=e.bank_account, hourly_rate=e.hourly_rate, nmw_band=e.nmw_band,
            basic_pay=round(base,2), overtime_hours=ot_hrs, overtime_pay=ot_pay, gross_pay=gross,
            paye_tax=tax, employee_ni=ni, employer_ni=er_ni, employee_pension=ee_pen,
            employer_pension=er_pen, student_loan=sl, net_pay=net, anomaly_type="none"))
pay = pd.DataFrame(recs)

# --- Inject anomalies (ground truth in `anomaly_type`) ---
def pick(n, mask=None):
    idx = pay.index if mask is None else pay.index[mask]
    return rng.choice(idx, n, replace=False)

# 1. NMW breach (hourly rate too low from some month onward)
for emp_id in rng.choice(emp.employee_id, 8, replace=False):
    band = emp.loc[emp.employee_id==emp_id,"nmw_band"].iloc[0]
    m = pay.employee_id==emp_id; pay.loc[m,"hourly_rate"] = round(NMW[band]-rng.uniform(0.3,1.5),2)
    pay.loc[m,"anomaly_type"] = "nmw_breach"
# 2. Duplicate payments
dups = pay.loc[pick(40)].copy(); dups["anomaly_type"]="duplicate_payment"
pay.loc[dups.index,"anomaly_type"]="duplicate_payment_original"
pay = pd.concat([pay, dups], ignore_index=True)
# 3. Overtime spike
i = pick(30); pay.loc[i,"overtime_hours"] += rng.uniform(40,80,30).round(1)
pay.loc[i,"overtime_pay"] = (pay.loc[i,"overtime_hours"]*pay.loc[i,"hourly_rate"]*1.5).round(2)
pay.loc[i,"gross_pay"] = (pay.loc[i,"basic_pay"]+pay.loc[i,"overtime_pay"]).round(2)
pay.loc[i,"net_pay"] = (pay.loc[i,"gross_pay"]*0.78).round(2); pay.loc[i,"anomaly_type"]="overtime_spike"
# 4. Tax underpaid (wrong tax code applied)
i = pick(30); pay.loc[i,"paye_tax"] = (pay.loc[i,"paye_tax"]*0.3).round(2)
pay.loc[i,"net_pay"] = (pay.loc[i,"gross_pay"]-pay.loc[i,"paye_tax"]-pay.loc[i,"employee_ni"]-pay.loc[i,"employee_pension"]-pay.loc[i,"student_loan"]).round(2)
pay.loc[i,"anomaly_type"]="tax_error"
# 5. Missing NI number
i = pick(15); pay.loc[i,"ni_number"] = None; pay.loc[i,"anomaly_type"]="missing_ni"
# 6. Negative net pay
i = pick(8); pay.loc[i,"net_pay"] = -pay.loc[i,"net_pay"]*0.1; pay.loc[i,"anomaly_type"]="negative_net_pay"
# 7. Ghost employees (no start record in HR, shared bank account, round salaries)
ghosts=[]
shared_bank = "99887766"
for g in range(1,5):
    gid=f"G{g:04d}"
    for m in MONTHS[rng.integers(0,6):]:
        ghosts.append(dict(pay_month=str(m), employee_id=gid, department=random.choice(dept_names),
          ni_number=ni_number(), bank_account=shared_bank, hourly_rate=15.0, nmw_band="21+",
          basic_pay=2500.0, overtime_hours=0.0, overtime_pay=0.0, gross_pay=2500.0,
          paye_tax=246.0, employee_ni=116.0, employer_ni=312.0, employee_pension=0.0,
          employer_pension=0.0, student_loan=0.0, net_pay=2138.0, anomaly_type="ghost_employee"))
pay = pd.concat([pay, pd.DataFrame(ghosts)], ignore_index=True)
pay.loc[pay.anomaly_type=="duplicate_payment_original","anomaly_type"]="none"
pay = pay.sample(frac=1, random_state=1).sort_values(["pay_month","employee_id"]).reset_index(drop=True)

emp.to_csv("/mnt/user-data/outputs/employees.csv", index=False)
pay.to_csv("/mnt/user-data/outputs/payroll_monthly.csv", index=False)
print(len(emp), len(pay)); print(pay.anomaly_type.value_counts())
