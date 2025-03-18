# OpenCart REST API (Django)

This repository contains a **Django-based REST API** for OpenCart, along with a **Postman collection** (`opencart.postman_collection.json`) to test API requests.

## 📂 API Overview

The API is built using **Django REST Framework (DRF)** and provides endpoints for managing customers, products, categories, articles, and more.

### **Customer Management**
- `POST /api/register/` - Register a new customer
- `POST /api/login/` - Customer login
- `GET /api/customers/` - Retrieve all customers
- `PUT /api/customers/{id}/` - Update customer details
- `DELETE /api/customers/{id}/` - Delete a customer
- `GET /api/customers/{id}/addresses/` - Get customer addresses
- `POST /api/customers/{id}/add_address/` - Add an address for a customer

### **Category Management**
- `POST /api/categories/` - Create a new category
- `DELETE /api/category/delete/{id}/` - Delete a category

### **Product Management**
- `GET /api/products/` - Retrieve all products
- `POST /api/products/` - Create a new product
- `PUT /api/products/{id}/` - Update an existing product
- `DELETE /api/products/{id}/` - Delete a product

### **Article Management**
- `POST /api/articles/` - Create an article
- `PUT /api/articles/{id}/` - Update an article
- `DELETE /api/articles/{id}/` - Delete an article
- `POST /api/articles/{id}/add_comment/` - Add a comment to an article

## 🚀 Installation & Setup

### **1. Clone the Repository**
```sh
git clone https://github.com/Kunalchaudhary1/opencart.git
cd opencart

## 📌 Notes
- Ensure that your OpenCart API is running before making requests.
- Some endpoints require authentication (login required).
- Modify request data as per your API setup.

---

💡 **Contributions and feedback are welcome!**  
If you encounter any issues, feel free to raise an issue or contribute to the project. 🚀