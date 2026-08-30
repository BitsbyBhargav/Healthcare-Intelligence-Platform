import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3

st.set_page_config(page_title="Healthcare DW Analytics", layout="wide")

st.title("🏥 Hospital Operational Analytics & Readmission Dashboard")
st.markdown("### Data Warehouse Business Intelligence Platform (Jury 1)")

# Connect to Data Warehouse
conn = sqlite3.connect('healthcare_dw.db')

# Load Data via SQL
fact_df = pd.read_sql_query("SELECT * FROM Fact_Admissions", conn)
patient_df = pd.read_sql_query("SELECT * FROM Dim_Patient", conn)

# Merge Fact and Dimension for visual rendering
merged_df = fact_df.merge(patient_df, on='patient_nbr')

# KPI Metrics Header
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Admissions", f"{len(fact_df):,}")
col2.metric("Avg Hospital Stay", f"{fact_df['time_in_hospital'].mean():.2f} Days")
col3.metric("Avg Medications", f"{fact_df['num_medications'].mean():.1f}")
col4.metric("30-Day Readmission Rate", f"{(fact_df['readmitted'] == '<30').mean()*100:.2f}%")

st.divider()

# Charts
c1, c2 = st.columns(2)

with c1:
    st.subheader("Roll-Up: Admissions & Avg Stay by Age Bracket")
    age_agg = merged_df.groupby('age').agg(
        Total_Admissions=('encounter_id', 'count'),
        Avg_Stay=('time_in_hospital', 'mean')
    ).reset_index()
    fig1 = px.bar(age_agg, x='age', y='Total_Admissions', color='Avg_Stay',
                  labels={'Total_Admissions': 'Admissions', 'age': 'Age Group'},
                  title="Hospital Utilization across Age Cohorts")
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    st.subheader("Slice: Readmission Outcome by Medication Intensity")
    med_slice = fact_df[fact_df['num_medications'] > 15]
    fig2 = px.histogram(med_slice, x='readmitted', color='readmitted',
                        title="Readmission Breakdown for Patients with >15 Medications")
    st.plotly_chart(fig2, use_container_width=True)

conn.close()