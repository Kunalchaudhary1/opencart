from rest_framework import serializers
from .models import Category, CategoryDescription, Product, ProductImage, ProductDiscount, ProductSpecial, ProductAttribute, ProductToCategory, Customer, Address, Article, ArticleDescription, ArticleComment, Api, ApiIp, ApiHistory, ProductDescription, CategoryFilter, CategoryPath, CategoryToLayout, CategoryToStore, CouponCategory
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.db import transaction, connection
import logging
import hashlib
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)

class CustomerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Customer
        fields = ['firstname', 'lastname', 'email', 'telephone', 'password']

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])  # Hash password
        return Customer.objects.create(**validated_data)

class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            user = Customer.objects.get(email=data['email'])
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        if not check_password(data['password'], user.password):
            raise serializers.ValidationError("Invalid email or password")

        return user

class CategoryFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryFilter
        fields = ['filter_id']

class CategoryPathSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryPath
        fields = ['path_id', 'level']

class CategoryToLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryToLayout
        fields = ['store_id', 'layout_id']

class CategoryToStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryToStore
        fields = ['store_id']

class CouponCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponCategory
        fields = ['coupon_id']

class CategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, write_only=True)
    description = serializers.CharField(required=False, default='', write_only=True)
    meta_title = serializers.CharField(required=False, default='', write_only=True)
    meta_description = serializers.CharField(required=False, default='', write_only=True)
    meta_keyword = serializers.CharField(required=False, default='', write_only=True)
    language_id = serializers.IntegerField(default=1, write_only=True)
    filters = CategoryFilterSerializer(many=True, required=False)
    paths = CategoryPathSerializer(many=True, required=False)
    layouts = CategoryToLayoutSerializer(many=True, required=False)
    stores = CategoryToStoreSerializer(many=True, required=False)
    coupons = CouponCategorySerializer(many=True, required=False)

    class Meta:
        model = Category
        fields = [
            'category_id', 'image', 'parent_id', 'column', 'sort_order', 'status',
            'name', 'description', 'meta_title', 'meta_description', 'meta_keyword',
            'language_id', 'filters', 'paths', 'layouts', 'stores', 'coupons'
        ]
        read_only_fields = ['category_id']

    def create(self, validated_data):
        # Extract description fields
        name = validated_data.pop('name')
        description = validated_data.pop('description', '')
        meta_title = validated_data.pop('meta_title', '')
        meta_description = validated_data.pop('meta_description', '')
        meta_keyword = validated_data.pop('meta_keyword', '')
        language_id = validated_data.pop('language_id', 1)

        # Extract related data
        filters_data = validated_data.pop('filters', [])
        paths_data = validated_data.pop('paths', [])
        layouts_data = validated_data.pop('layouts', [])
        stores_data = validated_data.pop('stores', [])
        coupons_data = validated_data.pop('coupons', [])

        # Create category first
        category = Category.objects.create(**validated_data)

        # Create category description
        CategoryDescription.objects.create(
            category_id=category.category_id,
            language_id=language_id,
            name=name,
            description=description,
            meta_title=meta_title,
            meta_description=meta_description,
            meta_keyword=meta_keyword
        )

        # Create related data
        for filter_data in filters_data:
            CategoryFilter.objects.create(category=category, **filter_data)

        for path_data in paths_data:
            CategoryPath.objects.create(category=category, **path_data)

        for layout_data in layouts_data:
            CategoryToLayout.objects.create(category=category, **layout_data)

        for store_data in stores_data:
            CategoryToStore.objects.create(category=category, **store_data)

        for coupon_data in coupons_data:
            CouponCategory.objects.create(category=category, **coupon_data)

        return category

    def update(self, instance, validated_data):
        # Extract description fields
        name = validated_data.pop('name', None)
        description = validated_data.pop('description', None)
        meta_title = validated_data.pop('meta_title', None)
        meta_description = validated_data.pop('meta_description', None)
        meta_keyword = validated_data.pop('meta_keyword', None)
        language_id = validated_data.pop('language_id', None)

        # Extract related data
        filters_data = validated_data.pop('filters', None)
        paths_data = validated_data.pop('paths', None)
        layouts_data = validated_data.pop('layouts', None)
        stores_data = validated_data.pop('stores', None)
        coupons_data = validated_data.pop('coupons', None)

        # Update category fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update description if provided
        if name is not None:
            CategoryDescription.objects.filter(category_id=instance.category_id).update(
                name=name,
                description=description,
                meta_title=meta_title,
                meta_description=meta_description,
                meta_keyword=meta_keyword,
                language_id=language_id
            )

        # Update related data if provided
        if filters_data is not None:
            instance.filters.all().delete()
            for filter_data in filters_data:
                CategoryFilter.objects.create(category=instance, **filter_data)

        if paths_data is not None:
            instance.paths.all().delete()
            for path_data in paths_data:
                CategoryPath.objects.create(category=instance, **path_data)

        if layouts_data is not None:
            instance.layouts.all().delete()
            for layout_data in layouts_data:
                CategoryToLayout.objects.create(category=instance, **layout_data)

        if stores_data is not None:
            instance.stores.all().delete()
            for store_data in stores_data:
                CategoryToStore.objects.create(category=instance, **store_data)

        if coupons_data is not None:
            instance.coupons.all().delete()
            for coupon_data in coupons_data:
                CouponCategory.objects.create(category=instance, **coupon_data)

        return instance

class ProductDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDescription
        fields = ['language_id', 'name', 'description', 'tag', 'meta_title', 'meta_description', 'meta_keyword']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image', 'sort_order']

class ProductToCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductToCategory
        fields = ['category_id']

class ProductSpecialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecial
        fields = ['customer_group_id', 'priority', 'price', 'date_start', 'date_end']

class ProductSerializer(serializers.ModelSerializer):
    descriptions = ProductDescriptionSerializer(many=True, required=False)
    images = ProductImageSerializer(many=True, required=False)
    categories = ProductToCategorySerializer(many=True, required=False)
    specials = ProductSpecialSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'product_id', 'model', 'sku', 'upc', 'ean', 'jan', 'isbn', 'mpn',
            'location', 'quantity', 'stock_status_id', 'image', 'manufacturer_id',
            'shipping', 'price', 'points', 'tax_class_id', 'date_available',
            'weight', 'weight_class_id', 'length', 'width', 'height',
            'length_class_id', 'subtract', 'minimum', 'sort_order', 'status',
            'date_added', 'date_modified', 'descriptions', 'images', 'categories',
            'specials'
        ]
        read_only_fields = ['product_id', 'date_added', 'date_modified']

    def create(self, validated_data):
        descriptions_data = validated_data.pop('descriptions', [])
        images_data = validated_data.pop('images', [])
        categories_data = validated_data.pop('categories', [])
        specials_data = validated_data.pop('specials', [])

        product = Product.objects.create(**validated_data)

        for description_data in descriptions_data:
            ProductDescription.objects.create(product=product, **description_data)

        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)

        for category_data in categories_data:
            ProductToCategory.objects.create(product=product, **category_data)

        for special_data in specials_data:
            ProductSpecial.objects.create(product=product, **special_data)

        return product

    def update(self, instance, validated_data):
        descriptions_data = validated_data.pop('descriptions', [])
        images_data = validated_data.pop('images', [])
        categories_data = validated_data.pop('categories', [])
        specials_data = validated_data.pop('specials', [])

        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update descriptions
        instance.productdescription_set.all().delete()
        for description_data in descriptions_data:
            ProductDescription.objects.create(product=instance, **description_data)

        # Update images
        instance.productimage_set.all().delete()
        for image_data in images_data:
            ProductImage.objects.create(product=instance, **image_data)

        # Update categories
        instance.producttocategory_set.all().delete()
        for category_data in categories_data:
            ProductToCategory.objects.create(product=instance, **category_data)

        # Update specials
        instance.productspecial_set.all().delete()
        for special_data in specials_data:
            ProductSpecial.objects.create(product=instance, **special_data)

        return instance

class ProductDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDiscount
        exclude = ['product_id', 'product_discount_id']

class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        exclude = ['product_id']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['address_id', 'firstname', 'lastname', 'company', 
                 'address_1', 'address_2', 'city', 'postcode', 
                 'country_id', 'zone_id', 'default', 'customer']
        read_only_fields = ['address_id', 'customer']

class CustomerSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Customer
        fields = ['customer_id', 'firstname', 'lastname', 'email', 
                 'telephone', 'password', 'status', 'addresses']
        read_only_fields = ['customer_id']

    def validate(self, data):
        logger.info(f"Validating customer data: {data}")
        # If this is an update operation
        if self.instance:
            logger.info(f"Update operation for customer {self.instance.customer_id}")
            # Check if email is being changed and already exists
            if 'email' in data and data['email'] != self.instance.email:
                if Customer.objects.filter(email=data['email']).exclude(customer_id=self.instance.customer_id).exists():
                    raise serializers.ValidationError({'email': 'This email is already in use.'})
        else:
            logger.info("Create operation")
            # For new customers
            if Customer.objects.filter(email=data.get('email', '')).exists():
                raise serializers.ValidationError({'email': 'This email is already in use.'})
        
        return data

    def update(self, instance, validated_data):
        logger.info(f"Updating customer {instance.customer_id} with data: {validated_data}")
        try:
            with transaction.atomic():
                if 'password' in validated_data:
                    validated_data['password'] = make_password(validated_data['password'])
                
                # Update fields
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                
                # Save the instance
                instance.save()
                logger.info(f"Customer {instance.customer_id} updated successfully")
                
                # Verify the update
                updated = Customer.objects.get(customer_id=instance.customer_id)
                logger.info(f"Verified updated data: {updated.__dict__}")
                
                return updated
        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}")
            raise serializers.ValidationError(f"Failed to update customer: {str(e)}")

    def create(self, validated_data):
        logger.info(f"Creating new customer with data: {validated_data}")
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class ArticleDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleDescription
        fields = ['language_id', 'name', 'description', 'image', 'tag',
                 'meta_title', 'meta_description', 'meta_keyword']

class ArticleCommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()

    class Meta:
        model = ArticleComment
        fields = ['article_comment_id', 'article', 'parent', 'customer',
                 'author', 'comment', 'rating', 'status', 'date_added', 'replies']
        read_only_fields = ['article_comment_id', 'article', 'date_added', 'customer']

    def get_replies(self, obj):
        replies = ArticleComment.objects.filter(parent=obj)
        serializer = ArticleCommentSerializer(replies, many=True)
        return serializer.data

class ArticleSerializer(serializers.ModelSerializer):
    descriptions = ArticleDescriptionSerializer(many=True, required=False)
    comments = ArticleCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Article
        fields = ['article_id', 'topic_id', 'author', 'rating', 
                 'status', 'date_added', 'date_modified', 
                 'descriptions', 'comments']
        read_only_fields = ['article_id', 'date_added', 'date_modified']
        extra_kwargs = {
            'topic_id': {'required': False}
        }

    def validate(self, data):
        # If this is a create operation (no instance exists)
        if not self.instance:
            if 'topic_id' not in data:
                raise serializers.ValidationError({'topic_id': 'This field is required for creation.'})
            if 'descriptions' not in data:
                raise serializers.ValidationError({'descriptions': 'This field is required for creation.'})
        return data

    def create(self, validated_data):
        descriptions_data = validated_data.pop('descriptions')
        try:
            with transaction.atomic():
                # Create the article first
                article = Article.objects.create(**validated_data)
                
                # Create descriptions using raw SQL to match OpenCart's structure
                with connection.cursor() as cursor:
                    for description in descriptions_data:
                        cursor.execute("""
                            INSERT INTO oc_article_description 
                            (article_id, language_id, name, description, image, tag, meta_title, meta_description, meta_keyword)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, [
                            article.article_id,
                            description['language_id'],
                            description['name'],
                            description['description'],
                            description.get('image', ''),
                            description.get('tag', ''),
                            description.get('meta_title', ''),
                            description.get('meta_description', ''),
                            description.get('meta_keyword', '')
                        ])
                
                return article
        except Exception as e:
            logger.error(f"Error creating article: {str(e)}")
            raise serializers.ValidationError({
                "message": "Error creating article",
                "error": str(e)
            })

    def update(self, instance, validated_data):
        descriptions_data = validated_data.pop('descriptions', None)
        
        try:
            with transaction.atomic():
                # Update article fields
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.save()

                # Update descriptions only if provided
                if descriptions_data is not None:
                    with connection.cursor() as cursor:
                        # Delete existing descriptions
                        cursor.execute("DELETE FROM oc_article_description WHERE article_id = %s", [instance.article_id])
                        
                        # Insert new descriptions
                        for description in descriptions_data:
                            cursor.execute("""
                                INSERT INTO oc_article_description 
                                (article_id, language_id, name, description, image, tag, meta_title, meta_description, meta_keyword)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, [
                                instance.article_id,
                                description['language_id'],
                                description['name'],
                                description['description'],
                                description.get('image', ''),
                                description.get('tag', ''),
                                description.get('meta_title', ''),
                                description.get('meta_description', ''),
                                description.get('meta_keyword', '')
                            ])

                return instance
        except Exception as e:
            logger.error(f"Error updating article: {str(e)}")
            raise serializers.ValidationError({
                "message": "Error updating article",
                "error": str(e)
            })

class ApiIpSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiIp
        fields = ['api_ip_id', 'ip']

class ApiHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiHistory
        fields = ['api_history_id', 'call', 'ip', 'date_added']

class ApiSerializer(serializers.ModelSerializer):
    allowed_ips = ApiIpSerializer(many=True, read_only=True)
    history = ApiHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Api
        fields = ['api_id', 'username', 'key', 'status', 
                 'date_added', 'date_modified', 'allowed_ips', 'history']

    def create(self, validated_data):
        # Generate a secure API key
        import secrets
        validated_data['key'] = secrets.token_urlsafe(32)
        return super().create(validated_data)
