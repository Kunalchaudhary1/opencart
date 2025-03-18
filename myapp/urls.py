from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, AddressViewSet, ArticleViewSet, ApiViewSet,
    RegisterAPI, LoginAPI, CategoryCreateAPI, CategoryDeleteAPI, ProductAPI
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'addresses', AddressViewSet)
router.register(r'articles', ArticleViewSet)
router.register(r'apis', ApiViewSet)

urlpatterns = [
    path('register/', RegisterAPI.as_view(), name='register'),
    path('login/', LoginAPI.as_view(), name='login'),
    path('categories/', CategoryCreateAPI.as_view(), name='category-create'),
    path('categories/<int:category_id>/', CategoryDeleteAPI.as_view(), name='category-delete'),
    path('products/', ProductAPI.as_view(), name='product-list'),
    path('products/<int:product_id>/', ProductAPI.as_view(), name='product-detail'),
    path('', include(router.urls)),
]