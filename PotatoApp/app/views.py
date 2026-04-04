from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
import csv
from io import TextIOWrapper
from datetime import datetime
import pandas as pd
from xgboost import XGBRegressor
import joblib
import os

# Create your views here.
def members(request):
    template = loader.get_template('potatoApp.html')
    return HttpResponse(template.render())

def FtoC(fahrenheit):
    celsius = (fahrenheit - 32) * 5.0/9.0
    return celsius
def toMM(inches):
    mm = inches * 25.4
    return mm

weather = []
def calculate(request):
    if request.method == "POST":
        #print(len(request.FILES))
        #print(list(request.POST))
        for key in request.POST:
            if key.startswith("irrigation_date_"):
                print(request.POST.get(key))
            if key.startswith("irrigation_amount_"):
                print(request.POST.get(key))
        
        weather_data = request.FILES.get("weather")
        weather_decoded_file = TextIOWrapper(weather_data.file, encoding='utf-8')
        weather_reader = csv.reader(weather_decoded_file)
        for row in weather_reader:
            weather.append(row)
        for i in range(5):
            weather.pop(0)
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
                gdd = (tmax + tmin) / 2 - 10
                if gdd < 0:
                    gdd = 0
                accGDD += gdd
                precip = toMM(float(row[11]))
                accMoist += precip
        irrigation_value = request.POST.get("irrigation")
        if irrigation_value:
            accMoist += toMM(float(irrigation_value))
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, "final_xgb_model1.pkl")
        scaler_path = os.path.join(script_dir, "scaler1.pkl")
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        cultivar_options = ['Alpine Russet', 'Clearwater', 'Dakota Russet', 'Easton','FL 1867', 'FL 2137', 'Hamlin', 'Ivory Russet', 'Lamoka','MN13142', 'MN13142Cold', 'Red Norland', 'Russet Burbank', 'Umatilla']
        expected_columns = ['acGDDs', 'acMoist', 'SPAD'] + \
                   [f'Cultivar_{c.replace(" ", "_")}' for c in cultivar_options[1:]]
        cultivar = request.POST.get("cultivar")
        cultivar_data = {f'Cultivar_{c.replace(" ", "_")}': 0 for c in cultivar_options}
        cultivar_data[f'Cultivar_{cultivar.replace(" ", "_")}'] = 1
        input_data = {
            "accGDD": [accGDD],
            "accMoist": [accMoist],
            "SPAD": [request.POST.get("spad_value")]
        }
        input_data.update(cultivar_data)
        input_df = pd.DataFrame(input_data)
        input_df = input_df.reindex(columns=expected_columns, fill_value=0)
        input_df_scaled = scaler.transform(input_df.values)
        prediction = model.predict(input_df_scaled)
        
        result = {"message": prediction.tolist()}
        return JsonResponse(result)
    else:
        return JsonResponse({"error": "Invalid request method."}, status=400)