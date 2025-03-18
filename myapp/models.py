from django.db import models
from django.utils import timezone
import logging

class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    customer_group_id = models.IntegerField(default=1)
    store_id = models.IntegerField(default=0)
    language_id = models.IntegerField(default=1)
    firstname = models.CharField(max_length=32)
    lastname = models.CharField(max_length=32)
    email = models.CharField(max_length=96, unique=True)
    telephone = models.CharField(max_length=32)
    password = models.CharField(max_length=255)  # OpenCart uses salted hash
    custom_field = models.TextField(blank=True, null=True)
    newsletter = models.IntegerField(default=0)
    ip = models.GenericIPAddressField(default='127.0.0.1', null=True, blank=True)
    status = models.IntegerField(default=1)
    safe = models.IntegerField(default=0)
    commenter = models.TextField(blank=True, null=True)
    token = models.CharField(max_length=255, blank=True, null=True)
    code = models.CharField(max_length=40, blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'oc_customer'

    def save(self, *args, **kwargs):
        if not self.date_added:
            self.date_added = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firstname} {self.lastname}"

class Address(models.Model):
    address_id = models.AutoField(primary_key=True)
    customer_id = models.IntegerField()
    firstname = models.CharField(max_length=32)
    lastname = models.CharField(max_length=32)
    company = models.CharField(max_length=40, blank=True, null=True)
    address_1 = models.CharField(max_length=128)
    address_2 = models.CharField(max_length=128, blank=True, null=True)
    city = models.CharField(max_length=128)
    postcode = models.CharField(max_length=10)
    country_id = models.IntegerField()
    zone_id = models.IntegerField()
    custom_field = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_address'

    def __str__(self):
        return f"{self.firstname} {self.lastname} - {self.address_1}"

class Article(models.Model):
    article_id = models.AutoField(primary_key=True)
    image = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    status = models.BooleanField(default=True)
    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'oc_article'

    def __str__(self):
        return f"Article {self.article_id}"

class ArticleDescription(models.Model):
    article_id = models.OneToOneField(Article, on_delete=models.DO_NOTHING, primary_key=True)
    language_id = models.IntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.CharField(max_length=255, blank=True, null=True)
    meta_keyword = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_article_description'

    def __str__(self):
        return f"{self.title} ({self.language_id})"

class ArticleComment(models.Model):
    article_comment_id = models.AutoField(primary_key=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='article_comments')
    author = models.CharField(max_length=64)
    comment = models.TextField()
    rating = models.IntegerField(default=0)
    status = models.IntegerField(default=1)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'oc_article_comment'

    def __str__(self):
        return f"Comment by {self.author} on Article {self.article_id}"

class Api(models.Model):
    api_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=64)
    key = models.TextField()
    status = models.IntegerField(default=1)
    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'oc_api'

    def __str__(self):
        return self.username

class ApiIp(models.Model):
    api_ip_id = models.AutoField(primary_key=True)
    api = models.ForeignKey(Api, on_delete=models.CASCADE, related_name='allowed_ips')
    ip = models.CharField(max_length=40)

    class Meta:
        db_table = 'oc_api_ip'

    def __str__(self):
        return f"{self.api.username} - {self.ip}"

class ApiHistory(models.Model):
    api_history_id = models.AutoField(primary_key=True)
    api = models.ForeignKey(Api, on_delete=models.CASCADE, related_name='history')
    call = models.CharField(max_length=32)
    ip = models.CharField(max_length=40)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'oc_api_history'

    def __str__(self):
        return f"{self.api.username} - {self.call}"

class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    image = models.CharField(max_length=255, blank=True, null=True)
    parent_id = models.IntegerField(blank=True, null=True)
    column = models.IntegerField(blank=True, null=True)
    sort_order = models.IntegerField(blank=True, null=True)
    status = models.IntegerField(blank=True, null=True)
    date_added = models.DateTimeField(blank=True, null=True)
    date_modified = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_category'

    def __str__(self):
        return f"Category {self.category_id}"

    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        logger.info(f"Saving category with data: {self.__dict__}")
        
        if not self.date_added:
            self.date_added = timezone.now()
        self.date_modified = timezone.now()
        
        try:
            result = super().save(*args, **kwargs)
            logger.info(f"Category saved successfully with ID: {self.category_id}")
            return result
        except Exception as e:
            logger.error(f"Error saving category: {str(e)}")
            raise

class CategoryDescription(models.Model):
    category = models.OneToOneField(Category, on_delete=models.CASCADE, db_column='category_id')
    language_id = models.IntegerField()
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.CharField(max_length=255, blank=True, null=True)
    meta_keyword = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_category_description'
        unique_together = (('category', 'language_id'),)

    def __str__(self):
        return f"{self.name} ({self.language_id})"

class CategoryFilter(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')
    filter_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'oc_category_filter'
        unique_together = (('category', 'filter_id'),)

    def __str__(self):
        return f"Filter {self.filter_id} for Category {self.category_id}"

class CategoryPath(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='paths', db_column='category_id')
    path_id = models.IntegerField()
    level = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_category_path'
        unique_together = (('category', 'path_id'),)

    def __str__(self):
        return f"Path {self.path_id} for Category {self.category_id}"

class CategoryToLayout(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')
    store_id = models.IntegerField()
    layout_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_category_to_layout'
        unique_together = (('category', 'store_id'),)

    def __str__(self):
        return f"Layout {self.layout_id} for Category {self.category_id} in Store {self.store_id}"

class CategoryToStore(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')
    store_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'oc_category_to_store'
        unique_together = (('category', 'store_id'),)

    def __str__(self):
        return f"Category {self.category_id} in Store {self.store_id}"

class CouponCategory(models.Model):
    coupon_id = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')

    class Meta:
        managed = False
        db_table = 'oc_coupon_category'
        unique_together = (('coupon_id', 'category'),)

    def __str__(self):
        return f"Coupon {self.coupon_id} for Category {self.category_id}"

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    model = models.CharField(max_length=64)
    sku = models.CharField(max_length=64, blank=True, null=True)
    upc = models.CharField(max_length=12, blank=True, null=True)
    ean = models.CharField(max_length=14, blank=True, null=True)
    jan = models.CharField(max_length=13, blank=True, null=True)
    isbn = models.CharField(max_length=13, blank=True, null=True)
    mpn = models.CharField(max_length=64, blank=True, null=True)
    location = models.CharField(max_length=128, blank=True, null=True)
    quantity = models.IntegerField(default=0)
    stock_status_id = models.IntegerField()
    image = models.CharField(max_length=255, blank=True, null=True)
    manufacturer_id = models.IntegerField()
    shipping = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=15, decimal_places=4, default=0.0000)
    points = models.IntegerField(default=0)
    tax_class_id = models.IntegerField()
    date_available = models.DateField(blank=True, null=True)
    weight = models.DecimalField(max_digits=15, decimal_places=8, default=0.00000000)
    weight_class_id = models.IntegerField(default=0)
    length = models.DecimalField(max_digits=15, decimal_places=8, default=0.00000000)
    width = models.DecimalField(max_digits=15, decimal_places=8, default=0.00000000)
    height = models.DecimalField(max_digits=15, decimal_places=8, default=0.00000000)
    length_class_id = models.IntegerField(default=0)
    subtract = models.BooleanField(default=True)
    minimum = models.IntegerField(default=1)
    sort_order = models.IntegerField(default=0)
    status = models.BooleanField(default=True)
    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'oc_product'

    def __str__(self):
        return f"Product {self.product_id}: {self.model}"

class ProductDescription(models.Model):
    product_id = models.OneToOneField(Product, on_delete=models.DO_NOTHING, primary_key=True)
    language_id = models.IntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    tag = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.CharField(max_length=255, blank=True, null=True)
    meta_keyword = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_product_description'

class ProductImage(models.Model):
    product_image_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField()
    image = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'oc_product_image'

class ProductToCategory(models.Model):
    product_id = models.IntegerField(primary_key=True)
    category_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'oc_product_to_category'

class ProductDiscount(models.Model):
    product_discount_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField()
    customer_group_id = models.IntegerField()
    quantity = models.IntegerField()
    priority = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=15, decimal_places=4)
    date_start = models.DateField()
    date_end = models.DateField()

    class Meta:
        db_table = 'oc_product_discount'
        managed = False

class ProductSpecial(models.Model):
    product_special_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField()
    customer_group_id = models.IntegerField()
    priority = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=15, decimal_places=4, default=0.0000)
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'oc_product_special'

class ProductAttribute(models.Model):
    product_id = models.IntegerField()
    attribute_id = models.IntegerField()
    language_id = models.IntegerField()
    text = models.TextField()

    class Meta:
        db_table = 'oc_product_attribute'
        managed = False
        unique_together = (('product_id', 'attribute_id', 'language_id'),)

# Create your models here.
