import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import find_peaks
import os
from datetime import date, time, timedelta, datetime
import datetime as dt
import random

##### Building Flight Class #####
class flight:
    flight_number = 0
    def __init__(self, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time
        self.duration = timedelta(
            hours = end_time.hour - start_time.hour,
            minutes = end_time.minute - start_time.minute,
            seconds = end_time.second - start_time.second)
        self.energy = 0.69*self.duration.seconds/60

        #self.duration = datetime.combine(date.today(),end_time)-datetime.combine(date.today(),start_time)

    def print_var(self):
        print('Start: ', self.start_time, ' End: ', self.end_time, ' Duration: ', self.duration)

##### Creating a plane class to store an array of flights #####
class plane:
    flight_array = []
    plane_type = ''
    tail_number = ''
    name = '2_Pax'
    energy_per_min = 0.0
    battery_capacity = 100
    origin_and_destination = 'APA'
    charge_rate = battery_capacity/30
    
    def clear_plane(self):
        self.flight_array.clear()

path = 'flight_data/'
files = os.listdir(path)

##### Building array of random planes to draw from. #####
plane_array = []
for filename in files:
    try:
        df = pd.read_excel(path+filename)
    except:
        continue
    
    # Assigning date to proper type
    df['Date'] = pd.to_datetime(df['Date'])

    for day in df['Date'].unique():

        flight_array = []

        mask = df['Date'] == day
        for entry in df[mask].index:
            start_time = df[mask].loc[entry, 'Departure Time']
            end_time = df[mask].loc[entry, 'Arrival Time']
            flight_array.append(flight(start_time, end_time))


        temp_plane = plane()
        temp_plane.flight_array = flight_array

        plane_array.append(temp_plane)
        # Add the ability to attach a plane type to the temp_plane class

###### Set up streamlit objects #####
st.title("Airplane Scheduler")
st.write('Input the number of planes and the linear energy burn rate and this code will create a synthetic schedule for the airplanes.')
# Getting the number of planes to simulate
number_of_planes = st.number_input(
    label = 'Enter the number of planes you wish to simulate.',
    min_value = 0,
    value = 10
)
# Getting linear energy burn rate
linear_burn_rate = st.number_input(
    label = 'Enter the linear energy burn rate of the planes in kWh/min.',
    min_value = 0.0,
    value = 0.69
)
# Getting charge rate
charge_rate = st.selectbox(
    label = 'Enter the charge rate.',
    options = ('1C', '2C', '4C')
)

# Using a button to run the calculation
run_calculation = st.button(
    label = 'Run Simulation'
)

##### Running the calculation if the button is pressed. #####
if run_calculation: 
    # Setting a schedule warning flag in case cannot reach schedule
    schedule_warning_flag = False

    # Building the plane array with plane tail number and linear burn rate
    output_plane_array = random.sample(plane_array, number_of_planes)
    i = 1
    for output_plane in output_plane_array:
        output_plane.tail_number = 'N'+str(i)
        output_plane.energy_per_min = linear_burn_rate
        if charge_rate == '1C':
            output_plane.charge_rate = output_plane.battery_capacity/60
        elif charge_rate == '2C':
            output_plane.charge_rate = output_plane.battery_capacity/30
        elif charge_rate == '4C':
            output_plane.charge_rate = output_plane.battery_capacity/15
        i+=1

    # Building Array to estimate number of chargers
    df_chargers = pd.DataFrame()
    time_delta = timedelta(hours = 23, minutes = 59)
    date = datetime(year = 2023, month = 10, day = 26, hour = 0, minute = 0, second = 0)
    df_chargers.index = pd.date_range(start = date, end = date+time_delta, freq = 'min')
    df_chargers['total']=0

    # Graphing Schedules
    fig = go.Figure()
    for plane_obj in output_plane_array:
        # Build a temporary dataframe to hold flight schedule and SOC
        df_temp = pd.DataFrame()
        time_delta = timedelta(hours = 23, minutes = 59)
        date = datetime(year = 2023, month = 10, day = 26, hour = 0, minute = 0, second = 0)
        df_temp.index = pd.date_range(start = date, end = date+time_delta, freq = 'min')
        # Setting columns to zero
        df_temp['status'] = 0
        df_temp['SOC'] = 1.0
        df_temp['charging'] = 0

        # Setting status to 1 while it is in the air
        for flight_obj in plane_obj.flight_array:
            start_time = flight_obj.start_time
            start_datetime = datetime.combine(date.date(), start_time)
            end_time = flight_obj.end_time
            end_datetime = datetime.combine(date.date(), end_time)
            temp_mask = (df_temp.index > start_datetime) & (df_temp.index < end_datetime)
            df_temp.loc[temp_mask, 'status'] = 1


        # Discharging and charging
        time_delta_min = timedelta(minutes = 1)
        for i in df_temp.index[1:]:
            if df_temp.loc[i,'status'] == 1:
                df_temp.loc[i,'SOC'] = df_temp.loc[i-time_delta_min,'SOC'] - plane_obj.energy_per_min/plane_obj.battery_capacity
            elif (df_temp.loc[i,'status'] == 0) & (df_temp.loc[i-time_delta_min,'SOC'] < 0.95):
                df_temp.loc[i,'status'] = -1
                df_temp.loc[i,'charging'] = -1
                df_temp.loc[i, 'SOC'] = df_temp.loc[i-time_delta_min, 'SOC'] + plane_obj.charge_rate/plane_obj.battery_capacity
            else:
                df_temp.loc[i,'SOC'] = df_temp.loc[i-time_delta_min,'SOC']

        # Adding graph to chart
        fig.add_trace(go.Scatter(
            x = df_temp.index.time,
            y = df_temp['status'],
            name = plane_obj.tail_number
        ))

        # Graphing SOC
        fig.add_trace(go.Scatter(
            x = df_temp.index.time,
            y = df_temp['SOC'],
            name = plane_obj.tail_number + 'SOC'
        ))

        # Adding status to chargers needed.
        df_chargers['total'] = df_chargers['total'] + df_temp['charging']

        if min(df_temp['SOC']) < 0.0:
            schedule_warning_flag = True

    # Adding an annotation for flying
    fig.add_annotation(text="Flying",
                  xref="paper", yref="paper",
                  x=0.0, y=1.1, showarrow=False)
    
    fig.add_annotation(text="Charging",
                  xref="paper", yref="paper",
                  x=0.0, y=-1.0, showarrow=False)

    if schedule_warning_flag:
        st.write('Warning, based on schedule and charge rates electrified flights cannot meet demand, try adjusting charge rate and re-running the simulation.')
    st.plotly_chart(fig)

    # Adding number of chargers graph
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x = df_chargers.index,
        y = df_chargers['total']
    ))
    st.write('Below are the number of chargers in use.')
    st.plotly_chart(fig2)
    st.write('Chargers needed: ', -1*min(df_chargers['total']))

    # Generating output
    output_columns = ['Name', 'Tail Number', 'Flight Number', 'Origin', 'Destination', 'Departure Time', 'Arrival Time', 'Electric Energy (kWh)', 'Delta SOC']
    df_output = pd.DataFrame(columns = output_columns)
    i = 0
    for output_plane in output_plane_array: 
        for output_flight in output_plane.flight_array:
            
            df_output.loc[i,'Name'] = output_plane.name
            df_output.loc[i,'Tail Number'] = output_plane.tail_number
            df_output.loc[i,'Flight Number'] = output_flight.flight_number
            df_output.loc[i,'Origin'] = output_plane.origin_and_destination
            df_output.loc[i,'Destination'] = output_plane.origin_and_destination
            # Add datetime mydatetime = dt.datetime.combine(dt.date.today(), mytime)
            df_output.loc[i,'Departure Time'] = datetime.combine(datetime.today(), output_flight.start_time)
            df_output.loc[i,'Arrival Time'] = datetime.combine(datetime.today(), output_flight.end_time)
            df_output.loc[i,'Electric Energy (kWh)'] = output_flight.energy
            df_output.loc[i,'Delta SOC'] = output_flight.energy/output_plane.battery_capacity

            i += 1
    # Adjusting the tail numbers
    df_output = df_output.sort_values(['Tail Number', 'Departure Time'])
    for tail_number in df_output['Tail Number'].unique():
        i = 1
        mask = df_output['Tail Number'] == tail_number
        for entry in df_output[mask].index:
            df_output.loc[entry, 'Flight Number'] = i
            i+=1
    # Restting the index
    df_output.index = [*range(len(df_output))]

    # Adding a download button
    csv = df_output.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Press to Download Flight Schedule",
        csv,
        "file.csv",
        "text/csv",
        key='download-csv'
    )













