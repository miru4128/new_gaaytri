from django.contrib import admin
from .models import User, FarmerProfile, DoctorProfile

admin.site.register(User)
admin.site.register(FarmerProfile)
admin.site.register(DoctorProfile)