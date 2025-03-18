from django.shortcuts import render
# Create your views here.
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.utils.crypto import get_random_string
from .models import Customer, Category, CategoryDescription, Product
from .serializers import CustomerRegisterSerializer, CustomerLoginSerializer, CategorySerializer, ProductSerializer
import logging
from django.db import transaction, connection
from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import (
    Customer, Address, Article, ArticleDescription,
    ArticleComment, Api, ApiIp, ApiHistory
)
from .serializers import (
    CustomerSerializer, AddressSerializer, ArticleSerializer,
    ArticleDescriptionSerializer, ArticleCommentSerializer,
    ApiSerializer, ApiIpSerializer, ApiHistorySerializer
)
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
import os

logger = logging.getLogger(__name__)

class RegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.token = get_random_string(40)  # Generate API token
            user.save()
            return Response({'message': 'Registration successful', 'token': user.token})
        return Response(serializer.errors, status=400)

class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = CustomerLoginSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data
                
                # Generate new token
                new_token = get_random_string(40)
                
                # Update user token in database
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE oc_customer 
                            SET token = %s
                            WHERE customer_id = %s
                        """, [new_token, user.customer_id])
                
                # Verify token was saved
                saved_user = Customer.objects.get(email=user.email)
                logger.info(f"Token saved for user {saved_user.email}: {saved_user.token}")
                
                if saved_user.token != new_token:
                    logger.error(f"Token mismatch! Generated: {new_token}, Saved: {saved_user.token}")
                    return Response({
                        'message': 'Login successful but token verification failed',
                        'token': new_token
                    }, status=status.HTTP_201_CREATED)
                
                return Response({
                    'message': 'Login successful',
                    'token': new_token,
                    'user': {
                        'customer_id': user.customer_id,
                        'firstname': user.firstname,
                        'lastname': user.lastname,
                        'email': user.email,
                        'telephone': user.telephone
                    }
                })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                'message': 'Login failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CategoryCreateAPI(APIView):
    permission_classes = [AllowAny]

    def clear_opencart_cache(self):
        try:
            with connection.cursor() as cursor:
                # Check which cache tables exist
                cache_tables = {
                    'cache': self.table_exists(cursor, 'oc_cache'),
                    'modification': self.table_exists(cursor, 'oc_modification'),
                    'category_image_cache': self.table_exists(cursor, 'oc_category_image_cache'),
                    'setting': self.table_exists(cursor, 'oc_setting')
                }
                
                # Clear all category-related caches from database if table exists
                if cache_tables['cache']:
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'category%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'menu%'")
                
                # Clear modification cache if table exists
                if cache_tables['modification']:
                    cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'category%'")
                
                # Clear image cache if exists
                if cache_tables['category_image_cache']:
                    cursor.execute("DELETE FROM oc_category_image_cache")
                
                # Refresh modification cache if setting table exists
                if cache_tables['setting']:
                    cursor.execute("UPDATE oc_setting SET value = NOW() WHERE `key` = 'config_modification'")
                
                # Clear storage cache directories if they exist
                cache_dirs = [
                    'system/storage/cache/',
                    'system/storage/modification/',
                    'image/cache/'
                ]
                
                for cache_dir in cache_dirs:
                    try:
                        if os.path.exists(cache_dir):
                            for file in os.listdir(cache_dir):
                                file_path = os.path.join(cache_dir, file)
                                try:
                                    if os.path.isfile(file_path):
                                        os.unlink(file_path)
                                except Exception as e:
                                    logger.warning(f"Error clearing cache directory {cache_dir}: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error accessing cache directory {cache_dir}: {str(e)}")
                        continue
                
                logger.info("OpenCart cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            # Don't raise the error since cache clearing is not critical
            # The category creation should continue even if cache clearing fails
            pass

    def table_exists(self, cursor, table_name):
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name = %s
        """, [table_name])
        return cursor.fetchone()[0] > 0

    def get(self, request):
        # Add GET method to check table structure
        try:
            with connection.cursor() as cursor:
                # Check if we can read from the table
                cursor.execute("SELECT * FROM oc_category LIMIT 1")
                existing_row = cursor.fetchone()
                logger.info(f"Existing row from oc_category: {existing_row}")

                # Get table structure
                cursor.execute("SHOW COLUMNS FROM oc_category")
                columns = cursor.fetchall()
                table_structure = [{"Field": col[0], "Type": col[1], "Null": col[2], "Key": col[3], "Default": col[4], "Extra": col[5]} for col in columns]
                return Response({
                    "table_structure": table_structure,
                    "sample_row": existing_row
                })
        except Exception as e:
            logger.error(f"Error getting table structure: {str(e)}")
            return Response({"error": str(e)}, status=500)

    def post(self, request):
        try:
            logger.info(f"Attempting to create category with data: {request.data}")
            
            serializer = CategorySerializer(data=request.data)
            if serializer.is_valid():
                logger.info(f"Data validated successfully: {serializer.validated_data}")
                
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # First verify we can read from the table
                        cursor.execute("SELECT COUNT(*) FROM oc_category")
                        count = cursor.fetchone()[0]
                        logger.info(f"Current count in oc_category: {count}")

                        # Insert into oc_category with explicit column names
                        insert_query = """
                            INSERT INTO oc_category 
                            (image, parent_id, `column`, sort_order, status, date_added, date_modified)
                            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                        """
                        params = [
                            serializer.validated_data.get('image', ''),
                            serializer.validated_data.get('parent_id', 0),
                            serializer.validated_data.get('column', 1),
                            serializer.validated_data.get('sort_order', 0),
                            serializer.validated_data.get('status', 1)
                        ]
                        logger.info(f"Executing insert query: {insert_query} with params: {params}")
                        cursor.execute(insert_query, params)
                        
                        # Verify the insert by getting the last ID
                        cursor.execute("SELECT LAST_INSERT_ID()")
                        category_id = cursor.fetchone()[0]
                        logger.info(f"Got category_id: {category_id}")

                        # Verify the row was actually inserted
                        cursor.execute("SELECT * FROM oc_category WHERE category_id = %s", [category_id])
                        inserted_row = cursor.fetchone()
                        logger.info(f"Inserted row data: {inserted_row}")

                        if not inserted_row:
                            raise Exception("Row was not actually inserted despite no error")

                        # Now insert the description
                        desc_query = """
                            INSERT INTO oc_category_description 
                            (category_id, language_id, name, description, meta_title, meta_description, meta_keyword)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        desc_params = [
                            category_id,
                            serializer.validated_data.get('language_id', 1),
                            serializer.validated_data.get('name', ''),
                            serializer.validated_data.get('description', ''),
                            serializer.validated_data.get('meta_title', ''),
                            serializer.validated_data.get('meta_description', ''),
                            serializer.validated_data.get('meta_keyword', '')
                        ]
                        logger.info(f"Executing description insert: {desc_query} with params: {desc_params}")
                        cursor.execute(desc_query, desc_params)

                        # Handle category path
                        parent_id = serializer.validated_data.get('parent_id', 0)
                        if parent_id > 0:
                            # Get parent category paths
                            cursor.execute("""
                                SELECT path_id, level 
                                FROM oc_category_path 
                                WHERE category_id = %s
                            """, [parent_id])
                            parent_paths = cursor.fetchall()
                            
                            # Insert paths for the new category
                            for parent_path in parent_paths:
                                cursor.execute("""
                                    INSERT INTO oc_category_path 
                                    (category_id, path_id, level)
                                    VALUES (%s, %s, %s)
                                """, [category_id, parent_path[0], parent_path[1]])
                            
                            # Add the new category's own path
                            cursor.execute("""
                                INSERT INTO oc_category_path 
                                (category_id, path_id, level)
                                VALUES (%s, %s, %s)
                            """, [category_id, category_id, len(parent_paths) + 1])
                        else:
                            # For root categories, just add their own path
                            cursor.execute("""
                                INSERT INTO oc_category_path 
                                (category_id, path_id, level)
                                VALUES (%s, %s, %s)
                            """, [category_id, category_id, 1])

                        # Insert filters if provided
                        filters_data = serializer.validated_data.get('filters', [])
                        if filters_data:
                            filter_query = """
                                INSERT INTO oc_category_filter (category_id, filter_id)
                                VALUES (%s, %s)
                            """
                            for filter_data in filters_data:
                                cursor.execute(filter_query, [category_id, filter_data['filter_id']])

                        # Insert layouts if provided
                        layouts_data = serializer.validated_data.get('layouts', [])
                        if layouts_data:
                            layout_query = """
                                INSERT INTO oc_category_to_layout (category_id, store_id, layout_id)
                                VALUES (%s, %s, %s)
                            """
                            for layout_data in layouts_data:
                                cursor.execute(layout_query, [
                                    category_id,
                                    layout_data['store_id'],
                                    layout_data.get('layout_id', 0)
                                ])

                        # Insert stores if provided
                        stores_data = serializer.validated_data.get('stores', [])
                        if stores_data:
                            store_query = """
                                INSERT INTO oc_category_to_store (category_id, store_id)
                                VALUES (%s, %s)
                            """
                            for store_data in stores_data:
                                cursor.execute(store_query, [category_id, store_data['store_id']])

                        # Insert coupons if provided
                        coupons_data = serializer.validated_data.get('coupons', [])
                        if coupons_data:
                            coupon_query = """
                                INSERT INTO oc_coupon_category (category_id, coupon_id)
                                VALUES (%s, %s)
                            """
                            for coupon_data in coupons_data:
                                cursor.execute(coupon_query, [category_id, coupon_data['coupon_id']])

                        # Commit the transaction explicitly
                        cursor.execute("COMMIT")
                        
                        # Clear OpenCart cache to reflect changes
                        self.clear_opencart_cache()
                        
                        return Response({
                            'message': 'Category created successfully',
                            'category_id': category_id,
                            'status': serializer.validated_data.get('status', 1),
                            'parent_id': serializer.validated_data.get('parent_id', 0),
                            'verification': inserted_row is not None
                        })
            
            logger.error(f"Validation failed: {serializer.errors}")
            return Response(serializer.errors, status=400)
        except Exception as e:
            logger.error(f"Error creating category: {str(e)}")
            return Response({
                'message': 'Error creating category',
                'error': str(e)
            }, status=500)

class CategoryDeleteAPI(APIView):
    permission_classes = [AllowAny]

    def delete(self, request, category_id):
        try:
            logger.info(f"Attempting to delete category with ID: {category_id}")
            
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # First check if category exists
                    cursor.execute("SELECT * FROM oc_category WHERE category_id = %s", [category_id])
                    category = cursor.fetchone()
                    logger.info(f"Found category: {category}")
                    
                    if not category:
                        logger.warning(f"Category {category_id} not found")
                        return Response({
                            'message': 'Error deleting category',
                            'error': f'Category with ID {category_id} not found'
                        }, status=404)
                    
                    # Check for child categories
                    cursor.execute("SELECT COUNT(*) FROM oc_category WHERE parent_id = %s", [category_id])
                    child_count = cursor.fetchone()[0]
                    if child_count > 0:
                        logger.warning(f"Category {category_id} has {child_count} child categories")
                        return Response({
                            'message': 'Error deleting category',
                            'error': f'Cannot delete category {category_id} because it has {child_count} child categories'
                        }, status=400)
                    
                    try:
                        # Delete from oc_category_description first
                        cursor.execute("DELETE FROM oc_category_description WHERE category_id = %s", [category_id])
                        desc_rows_deleted = cursor.rowcount
                        logger.info(f"Deleted {desc_rows_deleted} rows from oc_category_description")
                        
                        # Check for any other related tables that might have foreign keys
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM information_schema.KEY_COLUMN_USAGE 
                            WHERE REFERENCED_TABLE_NAME = 'oc_category' 
                            AND TABLE_SCHEMA = DATABASE()
                        """)
                        fk_count = cursor.fetchone()[0]
                        logger.info(f"Found {fk_count} foreign key relationships to oc_category")
                        
                        # Then delete from oc_category
                        cursor.execute("DELETE FROM oc_category WHERE category_id = %s", [category_id])
                        cat_rows_deleted = cursor.rowcount
                        logger.info(f"Deleted {cat_rows_deleted} rows from oc_category")
                        
                        # Verify deletion
                        cursor.execute("SELECT COUNT(*) FROM oc_category WHERE category_id = %s", [category_id])
                        remaining = cursor.fetchone()[0]
                        if remaining > 0:
                            logger.error(f"Category {category_id} still exists after deletion")
                            raise Exception("Category was not deleted successfully")
                        
                        return Response({
                            'message': 'Category deleted successfully',
                            'category_id': category_id,
                            'details': {
                                'category_rows_deleted': cat_rows_deleted,
                                'description_rows_deleted': desc_rows_deleted
                            }
                        })
                    except Exception as e:
                        logger.error(f"Database error while deleting: {str(e)}")
                        # Explicitly rollback the transaction
                        transaction.set_rollback(True)
                        raise
                    
        except Exception as e:
            logger.error(f"Error deleting category {category_id}: {str(e)}")
            return Response({
                'message': 'Error deleting category',
                'error': str(e),
                'category_id': category_id
            }, status=500)

class ProductAPI(APIView):
    permission_classes = [AllowAny]

    def clear_opencart_cache(self):
        try:
            with connection.cursor() as cursor:
                # Check which cache tables exist
                cache_tables = {
                    'cache': self.table_exists(cursor, 'oc_cache'),
                    'modification': self.table_exists(cursor, 'oc_modification'),
                    'product_image_cache': self.table_exists(cursor, 'oc_product_image_cache'),
                    'setting': self.table_exists(cursor, 'oc_setting')
                }
                
                # Clear all product-related caches from database if table exists
                if cache_tables['cache']:
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'product%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'category%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'manufacturer%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'information%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'menu%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'store%'")
                    cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'admin%'")  # Clear admin cache
                
                # Clear modification cache if table exists
                if cache_tables['modification']:
                    cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'product%'")
                    cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'category%'")
                    cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'store%'")
                    cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'admin%'")  # Clear admin modifications
                
                # Clear image cache if exists
                if cache_tables['product_image_cache']:
                    cursor.execute("DELETE FROM oc_product_image_cache")
                
                # Refresh modification cache if setting table exists
                if cache_tables['setting']:
                    cursor.execute("UPDATE oc_setting SET value = NOW() WHERE `key` = 'config_modification'")
                
                # Clear storage cache directories if they exist
                cache_dirs = [
                    'system/storage/cache/',
                    'system/storage/modification/',
                    'image/cache/',
                    'admin/storage/cache/',  # Clear admin cache directory
                    'admin/storage/modification/'  # Clear admin modification directory
                ]
                
                for cache_dir in cache_dirs:
                    try:
                        if os.path.exists(cache_dir):
                            for file in os.listdir(cache_dir):
                                file_path = os.path.join(cache_dir, file)
                                try:
                                    if os.path.isfile(file_path):
                                        os.unlink(file_path)
                                except Exception as e:
                                    logger.warning(f"Error clearing cache directory {cache_dir}: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error accessing cache directory {cache_dir}: {str(e)}")
                        continue
                
                logger.info("OpenCart cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            pass

    def get(self, request, product_id=None):
        try:
            response = None
            if product_id:
                # Get specific product
                product = Product.objects.get(product_id=product_id)
                serializer = ProductSerializer(product)
                response = Response(serializer.data)
            else:
                # List all products
                products = Product.objects.all()
                serializer = ProductSerializer(products, many=True)
                response = Response(serializer.data)
            
            # Add cache control headers
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            return response
        except Product.DoesNotExist:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": "Error fetching products", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            with transaction.atomic():
                serializer = ProductSerializer(data=request.data)
                if serializer.is_valid():
                    logger.info(f"Creating product with data: {request.data}")
                    
                    with connection.cursor() as cursor:
                        # Check which tables exist
                        tables = {
                            'product': self.table_exists(cursor, 'oc_product'),
                            'product_description': self.table_exists(cursor, 'oc_product_description'),
                            'product_to_category': self.table_exists(cursor, 'oc_product_to_category'),
                            'product_image': self.table_exists(cursor, 'oc_product_image'),
                            'product_special': self.table_exists(cursor, 'oc_product_special'),
                            'product_discount': self.table_exists(cursor, 'oc_product_discount'),
                            'product_attribute': self.table_exists(cursor, 'oc_product_attribute'),
                            'product_option': self.table_exists(cursor, 'oc_product_option'),
                            'product_option_value': self.table_exists(cursor, 'oc_product_option_value'),
                            'product_to_store': self.table_exists(cursor, 'oc_product_to_store')
                        }
                        
                        logger.info(f"Available tables: {tables}")

                        # 1. Insert into main product table
                        insert_query = """
                            INSERT INTO oc_product (
                                model, sku, upc, ean, jan, isbn, mpn, location, quantity,
                                stock_status_id, image, manufacturer_id, shipping, price,
                                points, tax_class_id, date_available, weight, weight_class_id,
                                length, width, height, length_class_id, subtract, minimum,
                                sort_order, status, date_added, date_modified
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                            )
                        """
                        params = [
                            serializer.validated_data.get('model', ''),
                            serializer.validated_data.get('sku', ''),
                            serializer.validated_data.get('upc', ''),
                            serializer.validated_data.get('ean', ''),
                            serializer.validated_data.get('jan', ''),
                            serializer.validated_data.get('isbn', ''),
                            serializer.validated_data.get('mpn', ''),
                            serializer.validated_data.get('location', ''),
                            serializer.validated_data.get('quantity', 0),
                            serializer.validated_data.get('stock_status_id', 7),
                            serializer.validated_data.get('image', ''),
                            serializer.validated_data.get('manufacturer_id', 1),
                            serializer.validated_data.get('shipping', True),
                            serializer.validated_data.get('price', 0.0000),
                            serializer.validated_data.get('points', 0),
                            serializer.validated_data.get('tax_class_id', 9),
                            serializer.validated_data.get('date_available', timezone.now().date()),
                            serializer.validated_data.get('weight', 0.00000000),
                            serializer.validated_data.get('weight_class_id', 1),
                            serializer.validated_data.get('length', 0.00000000),
                            serializer.validated_data.get('width', 0.00000000),
                            serializer.validated_data.get('height', 0.00000000),
                            serializer.validated_data.get('length_class_id', 1),
                            serializer.validated_data.get('subtract', True),
                            serializer.validated_data.get('minimum', 1),
                            serializer.validated_data.get('sort_order', 0),
                            serializer.validated_data.get('status', True)
                        ]
                        cursor.execute(insert_query, params)
                        
                        # Get the product ID
                        cursor.execute("SELECT LAST_INSERT_ID()")
                        product_id = cursor.fetchone()[0]
                        logger.info(f"Created product with ID: {product_id}")

                        # 2. Insert product descriptions
                        if tables['product_description'] and 'descriptions' in request.data:
                            for desc in request.data['descriptions']:
                                cursor.execute("""
                                    INSERT INTO oc_product_description 
                                    (product_id, language_id, name, description, tag, meta_title, 
                                    meta_description, meta_keyword)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, [
                                    product_id,
                                    desc.get('language_id', 1),
                                    desc.get('name', ''),
                                    desc.get('description', ''),
                                    desc.get('tag', ''),
                                    desc.get('meta_title', ''),
                                    desc.get('meta_description', ''),
                                    desc.get('meta_keyword', '')
                                ])

                        # 3. Insert product categories and ensure proper category paths
                        if tables['product_to_category']:
                            # Always add to at least one category
                            categories = request.data.get('categories', [])
                            if not categories:
                                # If no categories specified, add to a default category (usually 1)
                                categories = [{'category_id': 1}]
                            
                            for category in categories:
                                cursor.execute("""
                                    INSERT INTO oc_product_to_category (product_id, category_id)
                                    VALUES (%s, %s)
                                """, [product_id, category['category_id']])
                                
                                # Also add to parent categories
                                cursor.execute("""
                                    SELECT path_id 
                                    FROM oc_category_path 
                                    WHERE category_id = %s
                                """, [category['category_id']])
                                parent_paths = cursor.fetchall()
                                
                                for path in parent_paths:
                                    if path[0] != category['category_id']:  # Don't duplicate the main category
                                        cursor.execute("""
                                            INSERT INTO oc_product_to_category (product_id, category_id)
                                            VALUES (%s, %s)
                                        """, [product_id, path[0]])

                        # 4. Insert product images
                        if tables['product_image'] and 'images' in request.data:
                            for idx, image in enumerate(request.data['images']):
                                cursor.execute("""
                                    INSERT INTO oc_product_image (product_id, image, sort_order)
                                    VALUES (%s, %s, %s)
                                """, [product_id, image['image'], image.get('sort_order', idx)])

                        # 5. Insert product special prices
                        if tables['product_special'] and 'specials' in request.data:
                            for special in request.data['specials']:
                                cursor.execute("""
                                    INSERT INTO oc_product_special 
                                    (product_id, customer_group_id, priority, price, date_start, date_end)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, [
                                    product_id,
                                    special.get('customer_group_id', 1),
                                    special.get('priority', 0),
                                    special.get('price', 0),
                                    special.get('date_start'),
                                    special.get('date_end')
                                ])

                        # 6. Add product to stores - This is crucial for frontend visibility
                        if tables['product_to_store']:
                            # Get all store IDs
                            cursor.execute("SELECT store_id FROM oc_store")
                            stores = cursor.fetchall()
                            
                            # If no stores found, add to store 0 (default store)
                            if not stores:
                                stores = [(0,)]
                            
                            # Add product to all stores
                            for store in stores:
                                cursor.execute("""
                                    INSERT INTO oc_product_to_store (product_id, store_id)
                                    VALUES (%s, %s)
                                """, [product_id, store[0]])

                        # Clear the cache after all updates
                        self.clear_opencart_cache()
                        
                        # Return the created product
                        product = Product.objects.get(product_id=product_id)
                        result = ProductSerializer(product).data
                        logger.info(f"Successfully created product and all related data")
                        return Response(result, status=status.HTTP_201_CREATED)
                            
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            return Response({"message": "Error creating product", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def table_exists(self, cursor, table_name):
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name = %s
        """, [table_name])
        return cursor.fetchone()[0] > 0

    def put(self, request, product_id):
        try:
            with transaction.atomic():
                product = Product.objects.get(product_id=product_id)
                serializer = ProductSerializer(product, data=request.data)
                if serializer.is_valid():
                    logger.info(f"Updating product {product_id} with data: {request.data}")
                    
                    with connection.cursor() as cursor:
                        # Check which tables exist
                        tables = {
                            'product': self.table_exists(cursor, 'oc_product'),
                            'product_description': self.table_exists(cursor, 'oc_product_description'),
                            'product_to_category': self.table_exists(cursor, 'oc_product_to_category'),
                            'product_image': self.table_exists(cursor, 'oc_product_image'),
                            'product_special': self.table_exists(cursor, 'oc_product_special'),
                            'product_discount': self.table_exists(cursor, 'oc_product_discount'),
                            'product_attribute': self.table_exists(cursor, 'oc_product_attribute'),
                            'product_option': self.table_exists(cursor, 'oc_product_option'),
                            'product_option_value': self.table_exists(cursor, 'oc_product_option_value'),
                            'product_to_store': self.table_exists(cursor, 'oc_product_to_store')
                        }
                        
                        logger.info(f"Available tables: {tables}")

                        # 1. Update main product table
                        if tables['product']:
                            update_query = """
                                UPDATE oc_product 
                                SET model = %s,
                                    sku = %s,
                                    upc = %s,
                                    ean = %s,
                                    jan = %s,
                                    isbn = %s,
                                    mpn = %s,
                                    location = %s,
                                    quantity = %s,
                                    stock_status_id = %s,
                                    image = %s,
                                    manufacturer_id = %s,
                                    shipping = %s,
                                    price = %s,
                                    points = %s,
                                    tax_class_id = %s,
                                    date_available = %s,
                                    weight = %s,
                                    weight_class_id = %s,
                                    length = %s,
                                    width = %s,
                                    height = %s,
                                    length_class_id = %s,
                                    subtract = %s,
                                    minimum = %s,
                                    sort_order = %s,
                                    status = %s,
                                    date_modified = NOW()
                                WHERE product_id = %s
                            """
                            params = [
                                serializer.validated_data.get('model', product.model),
                                serializer.validated_data.get('sku', product.sku),
                                serializer.validated_data.get('upc', product.upc),
                                serializer.validated_data.get('ean', product.ean),
                                serializer.validated_data.get('jan', product.jan),
                                serializer.validated_data.get('isbn', product.isbn),
                                serializer.validated_data.get('mpn', product.mpn),
                                serializer.validated_data.get('location', product.location),
                                serializer.validated_data.get('quantity', product.quantity),
                                serializer.validated_data.get('stock_status_id', product.stock_status_id),
                                serializer.validated_data.get('image', product.image),
                                serializer.validated_data.get('manufacturer_id', product.manufacturer_id),
                                serializer.validated_data.get('shipping', product.shipping),
                                serializer.validated_data.get('price', product.price),
                                serializer.validated_data.get('points', product.points),
                                serializer.validated_data.get('tax_class_id', product.tax_class_id),
                                serializer.validated_data.get('date_available', product.date_available),
                                serializer.validated_data.get('weight', product.weight),
                                serializer.validated_data.get('weight_class_id', product.weight_class_id),
                                serializer.validated_data.get('length', product.length),
                                serializer.validated_data.get('width', product.width),
                                serializer.validated_data.get('height', product.height),
                                serializer.validated_data.get('length_class_id', product.length_class_id),
                                serializer.validated_data.get('subtract', product.subtract),
                                serializer.validated_data.get('minimum', product.minimum),
                                serializer.validated_data.get('sort_order', product.sort_order),
                                serializer.validated_data.get('status', product.status),
                                product_id
                            ]
                            cursor.execute(update_query, params)
                        
                        # 2. Update product descriptions
                        if tables['product_description'] and 'descriptions' in request.data:
                            cursor.execute("DELETE FROM oc_product_description WHERE product_id = %s", [product_id])
                            for desc in request.data['descriptions']:
                                cursor.execute("""
                                    INSERT INTO oc_product_description 
                                    (product_id, language_id, name, description, tag, meta_title, 
                                    meta_description, meta_keyword)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, [
                                    product_id,
                                    desc.get('language_id', 1),
                                    desc.get('name', ''),
                                    desc.get('description', ''),
                                    desc.get('tag', ''),
                                    desc.get('meta_title', ''),
                                    desc.get('meta_description', ''),
                                    desc.get('meta_keyword', '')
                                ])

                        # 3. Update product categories and ensure proper category paths
                        if tables['product_to_category'] and 'categories' in request.data:
                            cursor.execute("DELETE FROM oc_product_to_category WHERE product_id = %s", [product_id])
                            for category in request.data['categories']:
                                cursor.execute("""
                                    INSERT INTO oc_product_to_category (product_id, category_id)
                                    VALUES (%s, %s)
                                """, [product_id, category['category_id']])
                                
                                # Also add to parent categories
                                cursor.execute("""
                                    SELECT path_id 
                                    FROM oc_category_path 
                                    WHERE category_id = %s
                                """, [category['category_id']])
                                parent_paths = cursor.fetchall()
                                
                                for path in parent_paths:
                                    if path[0] != category['category_id']:  # Don't duplicate the main category
                                        cursor.execute("""
                                            INSERT INTO oc_product_to_category (product_id, category_id)
                                            VALUES (%s, %s)
                                        """, [product_id, path[0]])

                        # 4. Update product images
                        if tables['product_image'] and 'images' in request.data:
                            cursor.execute("DELETE FROM oc_product_image WHERE product_id = %s", [product_id])
                            for idx, image in enumerate(request.data['images']):
                                cursor.execute("""
                                    INSERT INTO oc_product_image (product_id, image, sort_order)
                                    VALUES (%s, %s, %s)
                                """, [product_id, image['image'], image.get('sort_order', idx)])

                        # 5. Update product special prices
                        if tables['product_special'] and 'specials' in request.data:
                            cursor.execute("DELETE FROM oc_product_special WHERE product_id = %s", [product_id])
                            for special in request.data['specials']:
                                cursor.execute("""
                                    INSERT INTO oc_product_special 
                                    (product_id, customer_group_id, priority, price, date_start, date_end)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, [
                                    product_id,
                                    special.get('customer_group_id', 1),
                                    special.get('priority', 0),
                                    special.get('price', 0),
                                    special.get('date_start'),
                                    special.get('date_end')
                                ])

                        # 6. Update product store assignments - This is crucial for admin visibility
                        if tables['product_to_store']:
                            # Get all store IDs including admin store
                            cursor.execute("SELECT store_id FROM oc_store")
                            stores = cursor.fetchall()
                            
                            # If no stores found, add to store 0 (default store)
                            if not stores:
                                stores = [(0,)]
                            
                            # Delete existing store assignments
                            cursor.execute("DELETE FROM oc_product_to_store WHERE product_id = %s", [product_id])
                            
                            # Add product to all stores including admin store
                            for store in stores:
                                cursor.execute("""
                                    INSERT INTO oc_product_to_store (product_id, store_id)
                                    VALUES (%s, %s)
                                """, [product_id, store[0]])

                        # Clear the cache after all updates
                        self.clear_opencart_cache()
                        
                        # Refresh the product instance
                        product.refresh_from_db()
                        
                        # Log successful update
                        logger.info(f"Successfully updated product {product_id} and all related tables")
                        
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Product.DoesNotExist:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            return Response({"message": "Error updating product", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, product_id):
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # First verify the product exists
                    cursor.execute("SELECT * FROM oc_product WHERE product_id = %s", [product_id])
                    product = cursor.fetchone()
                    if not product:
                        logger.warning(f"Product {product_id} not found before deletion")
                        return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
                    
                    logger.info(f"Starting deletion of product {product_id}")
                    
                    # Check which tables exist
                    tables = {
                        'product': self.table_exists(cursor, 'oc_product'),
                        'product_description': self.table_exists(cursor, 'oc_product_description'),
                        'product_to_category': self.table_exists(cursor, 'oc_product_to_category'),
                        'product_image': self.table_exists(cursor, 'oc_product_image'),
                        'product_special': self.table_exists(cursor, 'oc_product_special'),
                        'product_discount': self.table_exists(cursor, 'oc_product_discount'),
                        'product_attribute': self.table_exists(cursor, 'oc_product_attribute'),
                        'product_option': self.table_exists(cursor, 'oc_product_option'),
                        'product_option_value': self.table_exists(cursor, 'oc_product_option_value'),
                        'product_to_store': self.table_exists(cursor, 'oc_product_to_store'),
                        'cache': self.table_exists(cursor, 'oc_cache'),
                        'modification': self.table_exists(cursor, 'oc_modification'),
                        'setting': self.table_exists(cursor, 'oc_setting'),
                        'product_related': self.table_exists(cursor, 'oc_product_related'),
                        'product_reward': self.table_exists(cursor, 'oc_product_reward'),
                        'product_to_layout': self.table_exists(cursor, 'oc_product_to_layout'),
                        'product_recurring': self.table_exists(cursor, 'oc_product_recurring'),
                        'product_filter': self.table_exists(cursor, 'oc_product_filter'),
                        'product_download': self.table_exists(cursor, 'oc_product_download')
                    }
                    
                    logger.info(f"Available tables for deletion: {tables}")
                    
                    # First, clear all caches before deletion
                    if tables['cache']:
                        logger.info("Clearing cache tables")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'product%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'category%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'manufacturer%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'store%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'admin%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'menu%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'information%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'layout%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'theme%'")
                        cursor.execute("DELETE FROM oc_cache WHERE `key` LIKE 'template%'")
                    
                    if tables['modification']:
                        logger.info("Clearing modification cache")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'product%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'category%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'store%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'admin%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'menu%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'layout%'")
                        cursor.execute("DELETE FROM oc_modification WHERE code LIKE 'theme%'")
                    
                    if tables['setting']:
                        logger.info("Updating modification timestamp")
                        cursor.execute("UPDATE oc_setting SET value = NOW() WHERE `key` = 'config_modification'")
                    
                    # Delete from all related tables in the correct order
                    if tables['product_related']:
                        logger.info("Deleting from product_related")
                        cursor.execute("DELETE FROM oc_product_related WHERE product_id = %s", [product_id])
                        cursor.execute("DELETE FROM oc_product_related WHERE related_id = %s", [product_id])
                    
                    if tables['product_reward']:
                        logger.info("Deleting from product_reward")
                        cursor.execute("DELETE FROM oc_product_reward WHERE product_id = %s", [product_id])
                    
                    if tables['product_to_layout']:
                        logger.info("Deleting from product_to_layout")
                        cursor.execute("DELETE FROM oc_product_to_layout WHERE product_id = %s", [product_id])
                    
                    if tables['product_recurring']:
                        logger.info("Deleting from product_recurring")
                        cursor.execute("DELETE FROM oc_product_recurring WHERE product_id = %s", [product_id])
                    
                    if tables['product_filter']:
                        logger.info("Deleting from product_filter")
                        cursor.execute("DELETE FROM oc_product_filter WHERE product_id = %s", [product_id])
                    
                    if tables['product_download']:
                        logger.info("Deleting from product_download")
                        cursor.execute("DELETE FROM oc_product_download WHERE product_id = %s", [product_id])
                    
                    if tables['product_to_store']:
                        logger.info("Deleting from product_to_store")
                        cursor.execute("DELETE FROM oc_product_to_store WHERE product_id = %s", [product_id])
                    
                    if tables['product_option_value']:
                        logger.info("Deleting from product_option_value")
                        cursor.execute("DELETE FROM oc_product_option_value WHERE product_id = %s", [product_id])
                    
                    if tables['product_option']:
                        logger.info("Deleting from product_option")
                        cursor.execute("DELETE FROM oc_product_option WHERE product_id = %s", [product_id])
                    
                    if tables['product_attribute']:
                        logger.info("Deleting from product_attribute")
                        cursor.execute("DELETE FROM oc_product_attribute WHERE product_id = %s", [product_id])
                    
                    if tables['product_special']:
                        logger.info("Deleting from product_special")
                        cursor.execute("DELETE FROM oc_product_special WHERE product_id = %s", [product_id])
                    
                    if tables['product_discount']:
                        logger.info("Deleting from product_discount")
                        cursor.execute("DELETE FROM oc_product_discount WHERE product_id = %s", [product_id])
                    
                    if tables['product_image']:
                        logger.info("Deleting from product_image")
                        cursor.execute("DELETE FROM oc_product_image WHERE product_id = %s", [product_id])
                    
                    if tables['product_to_category']:
                        logger.info("Deleting from product_to_category")
                        cursor.execute("DELETE FROM oc_product_to_category WHERE product_id = %s", [product_id])
                    
                    if tables['product_description']:
                        logger.info("Deleting from product_description")
                        cursor.execute("DELETE FROM oc_product_description WHERE product_id = %s", [product_id])
                    
                    if tables['product']:
                        logger.info("Deleting from product table")
                        cursor.execute("DELETE FROM oc_product WHERE product_id = %s", [product_id])
                    
                    # Clear all cache directories
                    cache_dirs = [
                        'system/storage/cache/',
                        'system/storage/modification/',
                        'image/cache/',
                        'admin/storage/cache/',
                        'admin/storage/modification/',
                        'catalog/view/theme/default/template/product/',
                        'catalog/view/theme/default/template/category/',
                        'catalog/view/theme/default/template/common/',
                        'catalog/view/theme/default/template/checkout/',
                        'catalog/view/theme/default/template/account/',
                        'catalog/view/theme/default/template/error/',
                        'catalog/view/theme/default/template/information/',
                        'catalog/view/theme/default/template/module/',
                        'catalog/view/theme/default/template/payment/',
                        'catalog/view/theme/default/template/shipping/',
                        'catalog/view/theme/default/template/total/'
                    ]
                    
                    for cache_dir in cache_dirs:
                        try:
                            if os.path.exists(cache_dir):
                                logger.info(f"Clearing cache directory: {cache_dir}")
                                for file in os.listdir(cache_dir):
                                    file_path = os.path.join(cache_dir, file)
                                    try:
                                        if os.path.isfile(file_path):
                                            os.unlink(file_path)
                                    except Exception as e:
                                        logger.warning(f"Error clearing cache file {file_path}: {str(e)}")
                        except Exception as e:
                            logger.warning(f"Error accessing cache directory {cache_dir}: {str(e)}")
                            continue
                    
                    # Verify deletion in all tables
                    verification_tables = [
                        'oc_product', 'oc_product_description', 'oc_product_to_category',
                        'oc_product_image', 'oc_product_special', 'oc_product_discount',
                        'oc_product_attribute', 'oc_product_option', 'oc_product_option_value',
                        'oc_product_to_store', 'oc_product_related', 'oc_product_reward',
                        'oc_product_to_layout', 'oc_product_recurring', 'oc_product_filter',
                        'oc_product_download'
                    ]
                    
                    for table in verification_tables:
                        if self.table_exists(cursor, table):
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE product_id = %s", [product_id])
                            count = cursor.fetchone()[0]
                            if count > 0:
                                logger.error(f"Product {product_id} still has {count} entries in {table}")
                                raise Exception(f"Product deletion verification failed in {table}")
                    
                    # Force refresh of modification cache
                    if tables['setting']:
                        cursor.execute("UPDATE oc_setting SET value = NOW() WHERE `key` = 'config_modification'")
                    
                    logger.info(f"Successfully deleted product {product_id} and all related data")
                    return Response({"message": "Product deleted successfully"})
                    
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            return Response({"message": "Error deleting product", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            logger.info(f"Starting update for customer {instance.customer_id}")
            logger.info(f"Current data in DB: {instance.__dict__}")
            logger.info(f"Received data for update: {request.data}")

            # Validate the data first
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Direct SQL update without date_modified
                    update_query = """
                        UPDATE oc_customer 
                        SET firstname = %s,
                            lastname = %s,
                            email = %s,
                            telephone = %s
                        WHERE customer_id = %s
                    """
                    
                    params = [
                        request.data.get('firstname', instance.firstname),
                        request.data.get('lastname', instance.lastname),
                        request.data.get('email', instance.email),
                        request.data.get('telephone', instance.telephone),
                        instance.customer_id
                    ]
                    
                    logger.info(f"Executing update query: {update_query}")
                    logger.info(f"With parameters: {params}")
                    
                    cursor.execute(update_query, params)
                    rows_affected = cursor.rowcount
                    logger.info(f"Rows affected: {rows_affected}")
                    
                    if rows_affected == 0:
                        raise serializers.ValidationError("No rows were updated")
                    
                    # Verify the update
                    cursor.execute("""
                        SELECT customer_id, firstname, lastname, email, telephone, status
                        FROM oc_customer 
                        WHERE customer_id = %s
                    """, [instance.customer_id])
                    
                    updated_data = cursor.fetchone()
                    logger.info(f"Updated data in database: {updated_data}")
                    
                    if not updated_data:
                        raise serializers.ValidationError("Failed to verify update")
                    
                    # Refresh the instance
                    instance.refresh_from_db()
                    result = self.get_serializer(instance).data
                    logger.info(f"Final serialized data: {result}")
                    
                    # Verify the update was successful
                    if (result['firstname'] != request.data.get('firstname', result['firstname']) or
                        result['lastname'] != request.data.get('lastname', result['lastname']) or
                        result['email'] != request.data.get('email', result['email']) or
                        result['telephone'] != request.data.get('telephone', result['telephone'])):
                        logger.error("Data mismatch after update!")
                        logger.error(f"Expected: {request.data}")
                        logger.error(f"Got: {result}")
                        raise serializers.ValidationError("Update verification failed")
                    
                    return Response(result)
                    
        except serializers.ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}")
            return Response(
                {"error": "Failed to update customer", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def addresses(self, request, pk=None):
        customer = self.get_object()
        addresses = Address.objects.filter(customer=customer)
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_address(self, request, pk=None):
        customer = self.get_object()
        serializer = AddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(customer=customer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(customer_id=self.request.user.id)

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        article = self.get_object()
        comments = ArticleComment.objects.filter(article=article, parent=None)
        serializer = ArticleCommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        try:
            article = self.get_object()
            logger.info(f"Adding comment to article {article.article_id}")
            logger.info(f"Request data: {request.data}")
            
            # Add article to the request data
            comment_data = request.data.copy()
            
            serializer = ArticleCommentSerializer(data=comment_data)
            if serializer.is_valid():
                comment = serializer.save(
                    article=article,
                    status=1,  # Set default status
                    date_added=timezone.now()
                )
                logger.info(f"Comment created successfully with ID: {comment.article_comment_id}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            logger.error(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            return Response(
                {"error": "Failed to add comment", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reply_to_comment(self, request, pk=None):
        article = self.get_object()
        parent_comment_id = request.data.get('parent_comment_id')
        parent_comment = get_object_or_404(ArticleComment, article_comment_id=parent_comment_id)
        
        serializer = ArticleCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(article=article, parent=parent_comment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ApiViewSet(viewsets.ModelViewSet):
    queryset = Api.objects.all()
    serializer_class = ApiSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def add_ip(self, request, pk=None):
        api = self.get_object()
        serializer = ApiIpSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(api=api)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        api = self.get_object()
        history = ApiHistory.objects.filter(api=api)
        serializer = ApiHistorySerializer(history, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            api = serializer.save()
            # Log API creation
            logger.info(f"New API created: {api.username}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        # Log API deletion
        logger.info(f"API deleted: {instance.username}")
        instance.delete()
