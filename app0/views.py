from django.shortcuts import render

def main (request):
    return render(request, 'main.html')

def med (request):
    return render(request, 'med.html')

def bxod (request):
    return render(request, 'bxod.html')

def regist (request):
    return render(request, 'regist.html')

def table (request):
    return render(request, 'table.html')

def lk (request):
    return render(request, 'lk.html')
