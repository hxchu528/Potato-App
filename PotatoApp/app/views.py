from django.shortcuts import render
from django.template import loader
from django import forms
import io
import csv
from datetime import datetime
import pandas as pd
from xgboost import XGBRegressor
import joblib
import os

def FtoC(fahrenheit):
    celsius = (fahrenheit - 32) * 5.0/9.0
    return celsius

def toMM(inches):
    mm = inches * 25.4
    return mm

def validate_file(file):
    valid_extensions = ['.csv', '.xlsx']
    filename = file.name
    extension = os.path.splitext(filename)[1].lower()
    if extension not in valid_extensions:
        return False
    return True

def isNum(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def validate_input(request):
    if not validate_file(request.FILES["weather"]):
        return "Invalid file type. Please upload an Excel or CSV file."
    if (request.POST.get("spad_date") < request.POST.get("planting_date")):
        return "SPAD acquisition date must be after planting date."
    if not isNum(request.POST.get("spad_value")):
        return "SPAD value must be a number."
    if not isNum(request.POST.get("irrigation")) and request.POST.get("irrigation")!="":
        return "Irrigation value must be a number."
    return None

class Form(forms.Form):
    weather = forms.FileField(label="Weather file (Excel/CSV)")
    planting_date = forms.DateField(label="Planting date", widget=forms.DateInput(attrs={'type': 'date'}))
    spad_date = forms.DateField(label="SPAD reading date", widget=forms.DateInput(attrs={'type': 'date'}))
    spad_value = forms.FloatField(label="SPAD value")
    irrigation = forms.FloatField(label="Irrigation amount (inches)", required=False)
    cultivar = forms.ChoiceField(label="Cultivar", choices=[
        ('Alpine Russet', 'Alpine Russet'),
        ('Clearwater', 'Clearwater'),
        ('Dakota Russet', 'Dakota Russet'),
        ('Easton', 'Easton'),
        ('FL 1867', 'FL 1867'),
        ('FL 2137', 'FL 2137'),
        ('Hamlin', 'Hamlin'),
        ('Ivory Russet', 'Ivory Russet'),
        ('Lamoka', 'Lamoka'),
        ('MN13142', 'MN13142'),
        ('MN13142Cold', 'MN13142Cold'),
        ('Red Norland', 'Red Norland'),
        ('Russet Burbank', 'Russet Burbank'),
        ('Umatilla', 'Umatilla')
    ])

def ml_model(cultivar, accGDD, accMoist, spad_value):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "final_xgb_model1.pkl")
    scaler_path = os.path.join(script_dir, "scaler1.pkl")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    cultivar_options = ['Alpine Russet', 'Clearwater', 'Dakota Russet', 'Easton','FL 1867', 'FL 2137', 'Hamlin', 'Ivory Russet', 'Lamoka','MN13142', 'MN13142Cold', 'Red Norland', 'Russet Burbank', 'Umatilla']
    expected_columns = ['acGDDs', 'acMoist', 'SPAD'] + \
                   [f'Cultivar_{c.replace(" ", "_")}' for c in cultivar_options[1:]]
    cultivar_data = {f'Cultivar_{c.replace(" ", "_")}': 0 for c in cultivar_options}
    cultivar_data[f'Cultivar_{cultivar.replace(" ", "_")}'] = 1
    input_data = {
        "accGDD": [accGDD],
        "accMoist": [accMoist],
        "SPAD": [spad_value]
    }
    input_data.update(cultivar_data)
    input_df = pd.DataFrame(input_data)
    input_df = input_df.reindex(columns=expected_columns, fill_value=0)
    input_df_scaled = scaler.transform(input_df.values)
    prediction = model.predict(input_df_scaled)
    return prediction

def members(request):
    form = None
    if request.method == "POST":
        # Validate form data
        form = Form(request.POST)
        validation_error = validate_input(request)
        if validation_error:
            return render(request, 'potatoApp.html', {"message": validation_error,"form":form})
        # Get weather data
        weather_data = request.FILES["weather"]
        weather_decoded_file = weather_data.read().decode('utf-8')
        weather_decoded_file = io.StringIO(weather_decoded_file)
        if weather_data.name.endswith('.xlsx') or weather_data.name.endswith('.xls'):
            df = pd.read_excel(weather_decoded_file)
            weather_decoded_file = io.StringIO()
            df.to_csv(weather_decoded_file, index=False)
            weather_decoded_file.seek(0)
        weather_reader = csv.reader(weather_decoded_file)

        weather = []
        for row in weather_reader:
            weather.append(row)
        for i in range(5):
            weather.pop(0)
        
        # get weather data and calculate accumulated GDD and moisture
        planting_date = request.POST.get("planting_date")
        planting_date = datetime.strptime(planting_date, "%Y-%m-%d").date()
        spad_date = request.POST.get("spad_date")
        spad_date = datetime.strptime(spad_date, "%Y-%m-%d").date()
        accGDD = 0
        accMoist = 0
        for row in weather:
            date_str = row[4]+"-"+row[5]+"-"+row[6]
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date >= planting_date and date <= spad_date:
                tmax = FtoC(float(row[7]))
                tmin = FtoC(float(row[9]))
                gdd = (tmax + tmin) / 2 - 7
                if gdd < 0:
                    gdd = 0
                accGDD += gdd
                precip = toMM(float(row[11]))
                accMoist += precip
        irrigation_value = request.POST.get("irrigation")
        if irrigation_value!="":
            accMoist += toMM(float(irrigation_value))
        
        # Run ML model and return prediction
        prediction = ml_model(request.POST.get("cultivar"), accGDD, accMoist, float(request.POST.get("spad_value")))
        return render(request, 'potatoApp.html', {"message": f"Predicted PetioleNO3: {prediction[0]:.2f}","form": form})
    else:
        form = Form()
    return render(request, 'potatoApp.html', {"form": form})
