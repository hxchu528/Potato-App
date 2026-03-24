from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
import json


# Create your views here.
def members(request):
    template = loader.get_template('potatoApp.html')
    return HttpResponse(template.render())

def calculate(request):
    if request.method == "POST":
        data = request.FILES.get("weather")
        for chunk in data.chunks():
            print(chunk)
        # Perform calculations or processing with the received data
        result = {"message": "Data received successfully!"}
        return JsonResponse(result)
    else:
        return JsonResponse({"error": "Invalid request method."}, status=400)