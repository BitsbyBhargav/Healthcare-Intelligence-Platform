"""Hypothetical daily stock-and-flow scenarios, not a demand forecast."""
import json
import uuid
import pandas as pd
from healthline.warehouse import DEMO, connect, now


def simulate(beds, admissions, stay, discharge_rate, initial, days=14):
    if beds <= 0 or stay <= 0 or admissions < 0 or initial < 0 or not 0 <= discharge_rate <= 1:
        raise ValueError('Invalid scenario assumptions')
    # A sensitivity multiplier on LOS-implied turnover, not a learned clinical rate.
    occupancy = float(initial)
    rows = []
    for day in range(1,days+1):
        discharges = min(occupancy, occupancy/stay*discharge_rate)
        occupancy = max(0.,occupancy+admissions-discharges)
        rows.append({'day':day,'hypothetical_bed_demand':occupancy,
                     'capacity':beds,'pressure_pct':100*occupancy/beds,
                     'excess_demand':max(0.,occupancy-beds),'assumed_discharges':discharges})
    return pd.DataFrame(rows)


def save_scenario(assumptions, frame, path=DEMO):
    with connect(path) as c, c:
        c.execute('INSERT INTO operational_scenarios VALUES (?,?,?,?,?)',
                  (uuid.uuid4().hex,now(),'Hypothetical / Simulation',json.dumps(assumptions),frame.to_json(orient='records')))
