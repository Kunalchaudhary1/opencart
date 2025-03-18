from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from .models import Product
import json

class ProductAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product_data = {
            "model": "Test Product",
            "quantity": 100,
            "price": "99.99",
            "status": True,
            "descriptions": [
                {
                    "language_id": 1,
                    "name": "Test Product",
                    "description": "Test Description",
                    "meta_title": "Test Meta Title",
                    "meta_description": "Test Meta Description",
                    "meta_keyword": "test,product"
                }
            ],
            "categories": [
                {
                    "category_id": 1
                }
            ]
        }

    def test_create_product(self):
        response = self.client.post(
            reverse('product-list'),
            data=json.dumps(self.product_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(model="Test Product").exists())

    def test_get_product(self):
        # First create a product
        create_response = self.client.post(
            reverse('product-list'),
            data=json.dumps(self.product_data),
            content_type='application/json'
        )
        product_id = create_response.data['product_id']

        # Then retrieve it
        response = self.client.get(
            reverse('product-detail', kwargs={'product_id': product_id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['model'], "Test Product")

    def test_update_product(self):
        # First create a product
        create_response = self.client.post(
            reverse('product-list'),
            data=json.dumps(self.product_data),
            content_type='application/json'
        )
        product_id = create_response.data['product_id']

        # Update data
        update_data = self.product_data.copy()
        update_data['model'] = "Updated Test Product"

        # Then update it
        response = self.client.put(
            reverse('product-detail', kwargs={'product_id': product_id}),
            data=json.dumps(update_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['model'], "Updated Test Product")
