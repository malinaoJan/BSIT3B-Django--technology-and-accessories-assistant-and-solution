from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.home, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('accessories/', views.accessory_list, name='accessory_list'),
    path('solutions/', views.solution_list, name='solution_list'),
    path('brands/', views.brand_list, name='brand_list'),
    path('brands/<str:brand>/', views.brand_detail, name='brand_detail'),
]
