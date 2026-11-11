import os
import csv
import io
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from jinja2 import FunctionLoader

# ==========================================
# TEMPLATES DICTIONARY (IN-MEMORY)
# ==========================================
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Apple X - iPhone ERP{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        @media print {
            body { background-color: #fff !important; color: #000 !important; }
            /* Hide everything by default on print */
            body * { visibility: hidden !important; }
            
            /* Only show the vertical slips container and its contents */
            #verticalSlipsContainer, #verticalSlipsContainer * { visibility: visible !important; }
            
            #verticalSlipsContainer {
                position: absolute;
                left: 0;
                top: 0;
                width: 100%;
            }

            .vertical-slip {
                display: block !important;
                border: 2px dashed #000 !important;
                padding: 15px;
                margin-bottom: 20px;
                page-break-inside: avoid;
                font-family: monospace;
                font-size: 14px;
                color: #000 !important;
                background: #fff !important;
            }
            .vertical-slip h5 { border-bottom: 1px solid #000; padding-bottom: 5px; margin-bottom: 10px; font-weight: bold; }
            .vertical-slip .slip-row { display: flex; justify-content: space-between; margin-bottom: 4px; border-bottom: 1px dotted #ccc; padding-bottom: 2px; }
            .vertical-slip .slip-label { font-weight: bold; color: #333; }
        }
        .vertical-slip { display: none; }
    </style>
</head>
<body class="bg-body-tertiary">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark border-bottom px-4">
        <a class="navbar-brand fw-bold text-primary" href="/">Apple X | iPhone Inventory & POS (PKR)</a>
        <div class="navbar-nav ms-auto gap-3">
            <a class="nav-link {% if active == 'dashboard' %}active text-white fw-bold{% endif %}" href="/"><i class="bi bi-speedometer2"></i> Dashboard</a>
            <a class="nav-link {% if active == 'inventory' %}active text-white fw-bold{% endif %}" href="/inventory"><i class="bi bi-phone"></i> iPhone Inventory</a>
            <a class="nav-link {% if active == 'purchase' %}active text-white fw-bold{% endif %}" href="/purchase"><i class="bi bi-bag-plus"></i> Purchase Tab</a>
            <a class="nav-link {% if active == 'sale' %}active text-white fw-bold{% endif %}" href="/sale"><i class="bi bi-cart-check"></i> Sales Tab</a>
            <a class="nav-link {% if active == 'reports' %}active text-white fw-bold{% endif %}" href="/reports"><i class="bi bi-file-earmark-bar-graph"></i> Reports</a>
        </div>
    </nav>
    <div class="container my-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert alert-{{ cat }} alert-dismissible fade show" role="alert">
                        {{ msg }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block title %}Dashboard - Apple X{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>Apple X - Executive Dashboard & Profitability</h2>
    <div class="d-flex gap-2">
        <a href="/reports" class="btn btn-outline-success fw-bold"><i class="bi bi-file-earmark-bar-graph"></i> Advanced Reports</a>
        <a href="/inventory" class="btn btn-outline-info fw-bold"><i class="bi bi-phone"></i> View Inventory</a>
    </div>
</div>

<!-- IMEI Search Bar Card -->
<div class="card shadow-sm mb-4 bg-dark border-secondary">
    <div class="card-body">
        <form method="GET" action="/" class="row g-3 align-items-center">
            <div class="col-auto">
                <label class="fw-bold text-info"><i class="bi bi-search"></i> Instant IMEI Lookup:</label>
            </div>
            <div class="col-md-6">
                <input type="text" class="form-control" name="search_imei" value="{{ search_query }}" placeholder="Enter IMEI number..." required>
            </div>
            <div class="col-auto">
                <button type="submit" class="btn btn-primary fw-bold">Search Inventory</button>
                {% if search_query %}
                <a href="/" class="btn btn-outline-secondary ms-2">Reset</a>
                {% endif %}
            </div>
        </form>

        {% if search_query %}
        <hr class="border-secondary">
        <div class="mt-3">
            <h5 class="text-warning">Search Result for IMEI: <code>{{ search_query }}</code></h5>
            {% if search_result %}
            <div class="table-responsive">
                <table class="table table-sm table-dark table-bordered align-middle text-center mt-2">
                    <thead class="table-secondary text-dark">
                        <tr>
                            <th>Model</th>
                            <th>Storage / Color</th>
                            <th>PTA Status</th>
                            <th>Battery</th>
                            <th>Status</th>
                            <th>Cost</th>
                            <th>Purchase From</th>
                            <th>Sold To</th>
                            <th>Sold Price</th>
                            <th>Profit</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="fw-bold">{{ search_result.product.model }}</td>
                            <td>{{ search_result.product.storage }} / {{ search_result.product.color }}</td>
                            <td><span class="badge bg-secondary">{{ search_result.pta_status }}</span></td>
                            <td>{{ search_result.battery_health }}%</td>
                            <td>
                                <span class="badge bg-{{ 'success' if search_result.status == 'In Stock' else 'danger' }}">
                                    {{ search_result.status }}
                                </span>
                            </td>
                            <td class="text-warning">Rs. {{ search_result.purchase_cost }}</td>
                            <td class="text-info">{{ search_supplier_name }}</td>
                            <td>{{ search_customer_name }}</td>
                            <td class="text-primary">{{ search_sold_price }}</td>
                            <td class="text-success fw-bold">{{ search_profit }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="alert alert-danger mt-2 mb-0 py-2">❌ This IMEI is not from our inventory.</div>
            {% endif %}
        </div>
        {% endif %}
    </div>
</div>

<div class="row row-cols-1 row-cols-md-5 g-4 mb-4">
    <div class="col">
        <div class="card text-bg-primary shadow-sm h-100">
            <div class="card-body">
                <h6 class="card-title text-uppercase">Current Inventory Value</h6>
                <h3 class="card-text fw-bold">Rs. {{ "{:,.2f}".format(total_inv_value) }}</h3>
                <small>{{ total_units }} Units In Stock</small>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-secondary shadow-sm h-100">
            <div class="card-body">
                <h6 class="card-title text-uppercase">Total Purchase Revenue</h6>
                <h3 class="card-text fw-bold">Rs. {{ "{:,.2f}".format(total_purchase_revenue) }}</h3>
                <small>{{ total_units_purchased_count }} Units Purchased</small>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-success shadow-sm h-100">
            <div class="card-body">
                <h6 class="card-title text-uppercase">Total Sales Revenue</h6>
                <h3 class="card-text fw-bold">Rs. {{ "{:,.2f}".format(total_sales) }}</h3>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-warning shadow-sm h-100">
            <div class="card-body">
                <h6 class="card-title text-uppercase">Gross Profit</h6>
                <h3 class="card-text fw-bold">Rs. {{ "{:,.2f}".format(total_profit) }}</h3>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-{{ 'danger' if net_pnl < 0 else 'info' }} shadow-sm h-100">
            <div class="card-body">
                <h6 class="card-title text-uppercase">Net Profit / Loss</h6>
                <h3 class="card-text fw-bold">Rs. {{ "{:,.2f}".format(net_pnl) }}</h3>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-md-6">
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-dark fw-bold">Recent Purchases</div>
            <div class="card-body table-responsive">
                <table class="table table-sm table-dark align-middle">
                    <thead><tr><th>Date</th><th>Supplier</th><th>Model</th><th>Qty</th><th>Cost</th></tr></thead>
                    <tbody>
                        {% for p in recent_purchases %}
                        <tr>
                            <td>{{ p.date.strftime('%Y-%m-%d') }}</td>
                            <td>{{ p.supplier.name }}</td>
                            <td>{{ p.product.model }}</td>
                            <td>{{ p.quantity }}</td>
                            <td>Rs. {{ p.unit_cost }}</td>
                        </tr>
                        {% else %}
                        <tr><td colspan="5" class="text-center text-muted">No purchase records found.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-dark fw-bold">Recent Sales & Profit</div>
            <div class="card-body table-responsive">
                <table class="table table-sm table-dark align-middle">
                    <thead><tr><th>Date</th><th>Customer</th><th>Model</th><th>Qty</th><th>Price</th><th>Profit</th></tr></thead>
                    <tbody>
                        {% for s in recent_sales %}
                        <tr>
                            <td>{{ s.date.strftime('%Y-%m-%d') }}</td>
                            <td>{{ s.customer.name }}</td>
                            <td>{{ s.product.model }}</td>
                            <td>{{ s.quantity }}</td>
                            <td>Rs. {{ s.selling_price }}</td>
                            <td class="text-success fw-bold">+Rs. {{ s.gross_profit }}</td>
                        </tr>
                        {% else %}
                        <tr><td colspan="6" class="text-center text-muted">No sales records found.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

INVENTORY_TEMPLATE = """
{% extends "base" %}
{% block title %}Available Inventory - Apple X{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>📦 Available iPhone Inventory (In Stock)</h2>
    <span class="badge bg-success fs-5 p-2">{{ inventory_items|length }} Units Available</span>
</div>

<div class="card shadow-sm bg-dark border-secondary">
    <div class="card-body table-responsive">
        <table class="table table-dark table-striped table-bordered align-middle text-center">
            <thead class="table-secondary text-dark">
                <tr>
                    <th>Model</th>
                    <th>Storage / Color</th>
                    <th>PTA Status</th>
                    <th>IMEI</th>
                    <th>Battery Health</th>
                    <th>Purchase Cost</th>
                    <th>Purchase From</th>
                </tr>
            </thead>
            <tbody>
                {% for item in inventory_items %}
                <tr>
                    <td class="fw-bold">{{ item.product.model }}</td>
                    <td>{{ item.product.storage }} / {{ item.product.color }}</td>
                    <td><span class="badge bg-secondary">{{ item.pta_status }}</span></td>
                    <td><code>{{ item.imei1 if item.imei1 else 'N/A' }}</code></td>
                    <td><span class="badge bg-info text-dark">{{ item.battery_health }}%</span></td>
                    <td class="text-warning fw-bold">Rs. {{ item.purchase_cost }}</td>
                    <td class="text-info">{{ item.supplier_name }}</td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="7" class="text-center text-muted py-4">No iPhones currently in stock. Go to the Purchase Tab to add stock.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
"""

PURCHASE_TEMPLATE = """
{% extends "base" %}
{% block title %}Purchase Management - Apple X{% endblock %}
{% block content %}
<div class="row">
    <div class="col-md-4">
        <div class="card shadow-sm">
            <div class="card-header bg-primary fw-bold text-white"><i class="bi bi-bag-plus"></i> Purchase Inventory Form</div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Supplier name</label>
                        <input type="text" class="form-control" name="supplier_name" placeholder="e.g. Al-Madina Mobiles" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Supplier Mobile</label>
                        <input type="text" class="form-control" name="supplier_mobile" placeholder="0300..." required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">iPhone Model</label>
                        <select class="form-select" id="model_select" name="product_id" onchange="toggleCustomModel(this)">
                            {% for p in products %}
                            <option value="{{ p.id }}">{{ p.model }}</option>
                            {% endfor %}
                            <option value="CUSTOM">➕ Add Manually...</option>
                        </select>
                    </div>

                    <div id="custom_model_div" class="mb-3 d-none border p-2 rounded bg-dark">
                        <label class="form-label text-info small">Enter Custom iPhone Model</label>
                        <input type="text" class="form-control form-control-sm" name="custom_model" placeholder="e.g. iPhone Special Edition">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Storage</label>
                        <select class="form-select" name="storage">
                            <option value="64GB">64GB</option>
                            <option value="128GB" selected>128GB</option>
                            <option value="256GB">256GB</option>
                            <option value="512GB">512GB</option>
                            <option value="1TB">1TB</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Color</label>
                        <input type="text" class="form-control" name="color" placeholder="e.g. Space Gray, Gold" required>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">PTA Status</label>
                        <select class="form-select" name="pta_status">
                            <option value="PTA Approved" selected>PTA Approved</option>
                            <option value="Non-PTA">Non-PTA</option>
                            <option value="JV / Patch">JV / Patch</option>
                            <option value="CPID">CPID</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">IMEI (Optional)</label>
                        <input type="text" class="form-control" name="imei1" maxlength="15" placeholder="355... (optional)">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Quantity</label>
                        <input type="number" class="form-control" name="quantity" value="1" min="1" required>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Unit Price (PKR)</label>
                        <input type="number" step="0.01" class="form-control" name="unit_cost" placeholder="250000" required>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Battery Health %</label>
                        <input type="number" class="form-control" name="battery_health" value="100" min="1" max="100" required>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Payment Method</label>
                        <select class="form-select" name="payment_method">
                            <option value="Cash">Cash</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="JazzCash">JazzCash</option>
                            <option value="EasyPaisa">EasyPaisa</option>
                        </select>
                    </div>

                    <button type="submit" class="btn btn-primary w-100 fw-bold">Complete Purchase & Add Stock</button>
                </form>
            </div>
        </div>
    </div>
    <div class="col-md-8">
        <div class="card shadow-sm">
            <div class="card-header bg-dark fw-bold">Purchase Ledger History</div>
            <div class="card-body table-responsive">
                <table class="table table-dark table-striped align-middle">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Supplier</th>
                            <th>Supplier Phone</th>
                            <th>Model</th>
                            <th>Storage / Color</th>
                            <th>PTA</th>
                            <th>IMEI</th>
                            <th>Qty</th>
                            <th>Battery</th>
                            <th>Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in purchases %}
                        <tr>
                            <td>{{ p.date.strftime('%Y-%m-%d %H:%M') }}</td>
                            <td>{{ p.supplier.name }}</td>
                            <td><span class="text-info">{{ p.supplier.mobile }}</span></td>
                            <td>{{ p.product.model }}</td>
                            <td>{{ p.product.storage }} / {{ p.product.color }}</td>
                            <td><span class="badge bg-secondary">{{ p.pta_status }}</span></td>
                            <td><code>{{ p.imei1 if p.imei1 else '-' }}</code></td>
                            <td>{{ p.quantity }}</td>
                            <td>{{ p.battery_health }}%</td>
                            <td class="fw-bold text-warning">Rs. {{ p.unit_cost }}</td>
                        </tr>
                        {% else %}
                        <tr><td colspan="10" class="text-center text-muted">No purchases recorded yet.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
<script>
function toggleCustomModel(selectObj) {
    const customDiv = document.getElementById('custom_model_div');
    if (selectObj.value === 'CUSTOM') {
        customDiv.classList.remove('d-none');
    } else {
        customDiv.classList.add('d-none');
    }
}
</script>
{% endblock %}
"""

SALE_TEMPLATE = """
{% extends "base" %}
{% block title %}Sales POS - Apple X{% endblock %}
{% block content %}
<div class="row">
    <div class="col-md-5">
        <div class="card shadow-sm">
            <div class="card-header bg-success fw-bold text-white"><i class="bi bi-cart-check"></i> Multi-Unit POS Sales Terminal</div>
            <div class="card-body">
                <form method="POST" id="saleForm">
                    <div class="mb-3">
                        <label class="form-label">Customer Name</label>
                        <input type="text" class="form-control" name="customer_name" placeholder="Customer Name" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Customer Mobile</label>
                        <input type="text" class="form-control" name="customer_mobile" placeholder="0300..." required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Payment Method</label>
                        <select class="form-select" name="payment_method">
                            <option value="Cash">Cash</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="JazzCash">JazzCash</option>
                            <option value="EasyPaisa">EasyPaisa</option>
                        </select>
                    </div>

                    <hr class="border-secondary">
                    <h6 class="text-info fw-bold mb-2">Add Phones to Cart</h6>
                    
                    <div class="mb-3">
                        <label class="form-label small">Select In-Stock Phone</label>
                        <select class="form-select form-select-sm" id="phone_select">
                            {% for group in grouped_inventory %}
                            <option value="{{ group.product_id }}_{{ group.pta_status }}_{{ group.purchase_cost }}" data-model="{{ group.model }}" data-storage="{{ group.storage }}" data-color="{{ group.color }}" data-pta="{{ group.pta_status }}" data-cost="{{ group.purchase_cost }}" data-maxqty="{{ group.ids|length }}">
                            {{ group.model }} ({{ group.storage }} / {{ group.color }}) | PTA: {{ group.pta_status }} | In Stock Qty: {{ group.ids|length }} | Cost: Rs. {{ group.purchase_cost }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="form-label small">IMEI (Optional)</label>
                        <input type="text" class="form-control form-control-sm" id="cart_imei" maxlength="20" placeholder="Leave blank for auto-generate">
                    </div>

                    <div class="row g-2 mb-3">
                        <div class="col-6">
                            <label class="form-label small">Quantity</label>
                            <input type="number" class="form-control form-control-sm" id="cart_qty" value="1" min="1">
                        </div>
                        <div class="col-6">
                            <label class="form-label small">Selling Price (Per Unit PKR)</label>
                            <input type="number" step="0.01" class="form-control form-control-sm" id="cart_price" placeholder="275000">
                        </div>
                    </div>

                    <button type="button" class="btn btn-outline-info btn-sm w-100 mb-3 fw-bold" onclick="addCartItem()">➕ Add Phone to Sale Cart</button>

                    <!-- Hidden inputs container for form submission -->
                    <div id="cart_inputs"></div>

                    <button type="submit" class="btn btn-success w-100 fw-bold py-2" id="submitSaleBtn" disabled>Execute Multi-Unit Sale</button>
                </form>
            </div>
        </div>
    </div>

    <div class="col-md-7">
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-dark fw-bold">Current Sale Cart</div>
            <div class="card-body table-responsive">
                <table class="table table-sm table-dark table-striped align-middle text-center" id="cartTable">
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>PTA</th>
                            <th>IMEI</th>
                            <th>Qty</th>
                            <th>Price / Unit</th>
                            <th>Total</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr id="emptyCartRow">
                            <td colspan="7" class="text-muted py-3">Cart is empty. Add phones using the form on the left.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card shadow-sm">
            <div class="card-header bg-dark fw-bold">Recent Sales & Profit Records</div>
            <div class="card-body table-responsive">
                <table class="table table-dark table-striped align-middle small">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Model</th>
                            <th>PTA</th>
                            <th>IMEI</th>
                            <th>Qty</th>
                            <th>Price</th>
                            <th>Profit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for s in sales %}
                        <tr>
                            <td>{{ s.date.strftime('%Y-%m-%d %H:%M') }}</td>
                            <td>{{ s.customer.name }}</td>
                            <td>{{ s.product.model }}</td>
                            <td><span class="badge bg-secondary">{{ s.pta_status }}</span></td>
                            <td><code>{{ s.imei1 if s.imei1 else '-' }}</code></td>
                            <td>{{ s.quantity }}</td>
                            <td>Rs. {{ s.selling_price }}</td>
                            <td class="text-success fw-bold">+Rs. {{ s.gross_profit }}</td>
                        </tr>
                        {% else %}
                        <tr><td colspan="8" class="text-center text-muted">No sales completed yet.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
let cartItems = [];

function addCartItem() {
    const select = document.getElementById('phone_select');
    if (!select.options.length) {
        alert('No phones available in stock!');
        return;
    }
    const option = select.options[select.selectedIndex];
    const groupKey = option.value;
    const model = option.getAttribute('data-model');
    const storage = option.getAttribute('data-storage');
    const color = option.getAttribute('data-color');
    const pta = option.getAttribute('data-pta');
    const cost = parseFloat(option.getAttribute('data-cost'));
    const maxQty = parseInt(option.getAttribute('data-maxqty')) || 1;
    
    const qty = parseInt(document.getElementById('cart_qty').value) || 1;
    const price = parseFloat(document.getElementById('cart_price').value);
    const imeiInput = document.getElementById('cart_imei').value.trim();

    if (isNaN(price) || price <= 0) {
        alert('Please enter a valid selling price per unit.');
        return;
    }

    if (qty > maxQty) {
        alert(`Cannot sell ${qty} units. Only ${maxQty} units available in stock for this configuration.`);
        return;
    }

    cartItems.push({
        groupKey: groupKey,
        model: `${model} (${storage} / ${color})`,
        pta: pta,
        qty: qty,
        price: price,
        cost: cost,
        imeiInput: imeiInput
    });

    renderCart();
    document.getElementById('cart_imei').value = '';
}

function removeCartItem(index) {
    cartItems.splice(index, 1);
    renderCart();
}

function renderCart() {
    const tbody = document.querySelector('#cartTable tbody');
    const inputsContainer = document.getElementById('cart_inputs');
    const submitBtn = document.getElementById('submitSaleBtn');
    
    tbody.innerHTML = '';
    inputsContainer.innerHTML = '';

    if (cartItems.length === 0) {
        tbody.innerHTML = '<tr id="emptyCartRow"><td colspan="7" class="text-muted py-3">Cart is empty. Add phones using the form on the left.</td></tr>';
        submitBtn.disabled = true;
        return;
    }

    submitBtn.disabled = false;

    cartItems.forEach((item, index) => {
        const total = item.qty * item.price;
        
        // Render row in table
        tbody.innerHTML += `
            <tr>
                <td class="fw-bold">${item.model}</td>
                <td><span class="badge bg-secondary">${item.pta}</span></td>
                <td><code>${item.imeiInput ? item.imeiInput : 'Auto-Generate'}</code></td>
                <td>${item.qty}</td>
                <td>Rs. ${item.price.toLocaleString()}</td>
                <td class="text-warning">Rs. ${total.toLocaleString()}</td>
                <td><button type="button" class="btn btn-outline-danger btn-sm py-0" onclick="removeCartItem(${index})"><i class="bi bi-trash"></i></button></td>
            </tr>
        `;

        // Render hidden inputs for Flask POST submission
        inputsContainer.innerHTML += `
            <input type="hidden" name="items-${index}-group_key" value="${item.groupKey}">
            <input type="hidden" name="items-${index}-quantity" value="${item.qty}">
            <input type="hidden" name="items-${index}-selling_price" value="${item.price}">
            <input type="hidden" name="items-${index}-imei_input" value="${item.imeiInput}">
        `;
    });
}
</script>
{% endblock %}
"""

REPORTS_TEMPLATE = """
{% extends "base" %}
{% block title %}Reports & Analytics - Apple X{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>📊 Sales & Purchases Reporting Dashboard</h2>
    <div class="d-flex gap-2 no-print">
        <button onclick="printSelectedVerticalSlips()" class="btn btn-primary fw-bold"><i class="bi bi-printer"></i> Print Selected (Vertical Slip)</button>
        <button onclick="window.print()" class="btn btn-outline-light fw-bold"><i class="bi bi-printer"></i> Print All Report</button>
        <a href="/reports/export/csv?{{ request.query_string.decode('utf-8') }}" class="btn btn-success fw-bold"><i class="bi bi-file-earmark-spreadsheet"></i> Export to CSV</a>
    </div>
</div>

<!-- Filters Card -->
<div class="card shadow-sm mb-4 bg-dark border-secondary no-print">
    <div class="card-header bg-secondary text-dark fw-bold"><i class="bi bi-funnel"></i> Report Filters & Controls</div>
    <div class="card-body">
        <form method="GET" action="/reports" class="row g-3">
            <div class="col-md-3">
                <label class="form-label small">Quick Date Range</label>
                <select class="form-select form-select-sm" name="quick_range" onchange="handleQuickRange(this.value)">
                    <option value="">Custom / All Time</option>
                    <option value="today" {% if quick_range == 'today' %}selected{% endif %}>Today</option>
                    <option value="yesterday" {% if quick_range == 'yesterday' %}selected{% endif %}>Yesterday</option>
                    <option value="this_week" {% if quick_range == 'this_week' %}selected{% endif %}>This Week</option>
                    <option value="this_month" {% if quick_range == 'this_month' %}selected{% endif %}>This Month</option>
                    <option value="last_month" {% if quick_range == 'last_month' %}selected{% endif %}>Last Month</option>
                    <option value="this_year" {% if quick_range == 'this_year' %}selected{% endif %}>This Year</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label small">Transaction Type</label>
                <select class="form-select form-select-sm" name="tx_type">
                    <option value="all" {% if tx_type == 'all' %}selected{% endif %}>All Transactions (Sales & Purchases)</option>
                    <option value="sales" {% if tx_type == 'sales' %}selected{% endif %}>Sales Only</option>
                    <option value="purchases" {% if tx_type == 'purchases' %}selected{% endif %}>Purchases Only</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label small">iPhone Model</label>
                <select class="form-select form-select-sm" name="model_id">
                    <option value="">All Models</option>
                    {% for p in all_products %}
                    <option value="{{ p.id }}" {% if model_id == p.id|string %}selected{% endif %}>{{ p.model }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label small">Storage</label>
                <select class="form-select form-select-sm" name="storage">
                    <option value="">All Storages</option>
                    <option value="64GB" {% if storage == '64GB' %}selected{% endif %}>64GB</option>
                    <option value="128GB" {% if storage == '128GB' %}selected{% endif %}>128GB</option>
                    <option value="256GB" {% if storage == '256GB' %}selected{% endif %}>256GB</option>
                    <option value="512GB" {% if storage == '512GB' %}selected{% endif %}>512GB</option>
                    <option value="1TB" {% if storage == '1TB' %}selected{% endif %}>1TB</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label small">Customer / Supplier Name</label>
                <input type="text" class="form-control form-control-sm" name="partner_name" value="{{ partner_name }}" placeholder="Filter by name...">
            </div>
            <div class="col-md-3">
                <label class="form-label small">Date From</label>
                <input type="date" class="form-control form-control-sm" id="date_from" name="date_from" value="{{ date_from }}">
            </div>
            <div class="col-md-3">
                <label class="form-label small">Date To</label>
                <input type="date" class="form-control form-control-sm" id="date_to" name="date_to" value="{{ date_to }}">
            </div>
            <div class="col-12 d-flex justify-content-end gap-2 mt-3">
                <a href="/reports" class="btn btn-outline-secondary btn-sm">Clear Filters</a>
                <button type="submit" class="btn btn-primary btn-sm fw-bold px-4">Apply Filters</button>
            </div>
        </form>
    </div>
</div>

<!-- Live KPI Summary Cards -->
<div class="row row-cols-1 row-cols-md-3 row-cols-lg-6 g-3 mb-4">
    <div class="col">
        <div class="card text-bg-primary shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-white-50">Total Sales Amount</h6>
                <h5 class="card-text fw-bold">Rs. {{ "{:,.0f}".format(total_sales_amt) }}</h5>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-secondary shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-white-50">Total Purchase Amount</h6>
                <h5 class="card-text fw-bold">Rs. {{ "{:,.0f}".format(total_purchase_amt) }}</h5>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-warning shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-dark fw-bold">Gross Profit</h6>
                <h5 class="card-text fw-bold text-dark">Rs. {{ "{:,.0f}".format(total_profit) }}</h5>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-success shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-white-50">Units Sold</h6>
                <h5 class="card-text fw-bold">{{ total_units_sold }}</h5>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-info shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-dark fw-bold">Units Purchased</h6>
                <h5 class="card-text fw-bold text-dark">{{ total_units_purchased }}</h5>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card text-bg-dark border-secondary shadow-sm h-100">
            <div class="card-body p-3">
                <h6 class="card-title text-uppercase small text-white-50">Total Transactions</h6>
                <h5 class="card-text fw-bold">{{ unified_transactions|length }}</h5>
            </div>
        </div>
    </div>
</div>

<!-- Container for Generated Vertical Slips on Print -->
<div id="verticalSlipsContainer"></div>

<!-- Detailed Table Section -->
<div class="card shadow-sm bg-dark border-secondary" id="reportsTableCard">
    <div class="card-header bg-secondary text-dark fw-bold d-flex justify-content-between align-items-center">
        <span><i class="bi bi-table"></i> Detailed Transaction Ledger</span>
        <span class="badge bg-dark text-white">{{ unified_transactions|length }} Records Found</span>
    </div>
    <div class="card-body table-responsive">
        <table class="table table-dark table-striped table-bordered align-middle text-center small" id="reportsTable">
            <thead class="table-light text-dark">
                <tr>
                    <th class="no-print"><input type="checkbox" id="selectAllCheckbox" onchange="toggleSelectAll(this)"></th>
                    <th>Date & Time</th>
                    <th>Type</th>
                    <th>iPhone Model</th>
                    <th>Storage / Color</th>
                    <th>PTA Status</th>
                    <th>IMEI</th>
                    <th>Qty</th>
                    <th>Purchase Price</th>
                    <th>Sale Price</th>
                    <th class="no-print-col">Profit / Loss</th>
                    <th>Partner (Customer / Supplier)</th>
                    <th>Payment Method</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for tx in unified_transactions %}
                <tr class="tx-row" 
                    data-datetime="{{ tx.date.strftime('%Y-%m-%d %H:%M') }}"
                    data-type="{{ tx.type }}"
                    data-model="{{ tx.model }}"
                    data-storagecolor="{{ tx.storage }} / {{ tx.color }}"
                    data-ptastatus="{{ tx.pta_status }}"
                    data-imei="{{ tx.imei if tx.imei else '-' }}"
                    data-qty="{{ tx.qty }}"
                    data-saleprice="{% if tx.sale_price != '-' %}Rs. {{ tx.sale_price }}{% else %}-{% endif %}"
                    data-partner="{{ tx.partner }}"
                    data-paymentmethod="{{ tx.payment_method }}"
                    data-status="{{ tx.status }}">
                    <td class="no-print"><input type="checkbox" class="tx-checkbox" onchange="handleRowSelect(this)"></td>
                    <td>{{ tx.date.strftime('%Y-%m-%d %H:%M') }}</td>
                    <td>
                        <span class="badge bg-{{ 'success' if tx.type == 'Sale' else 'primary' }}">
                            {{ tx.type }}
                        </span>
                    </td>
                    <td class="fw-bold">{{ tx.model }}</td>
                    <td>{{ tx.storage }} / {{ tx.color }}</td>
                    <td><span class="badge bg-secondary">{{ tx.pta_status }}</span></td>
                    <td><code>{{ tx.imei if tx.imei else '-' }}</code></td>
                    <td>{{ tx.qty }}</td>
                    <td class="text-warning">{% if tx.purchase_price != '-' %}Rs. {{ tx.purchase_price }}{% else %}-{% endif %}</td>
                    <td class="text-primary">{% if tx.sale_price != '-' %}Rs. {{ tx.sale_price }}{% else %}-{% endif %}</td>
                    <td class="fw-bold no-print-col {{ 'text-success' if tx.profit != '-' and tx.profit >= 0 else 'text-danger' }}">
                        {% if tx.profit != '-' %}Rs. {{ tx.profit }}{% else %}-{% endif %}
                    </td>
                    <td class="text-info">{{ tx.partner }}</td>
                    <td>{{ tx.payment_method }}</td>
                    <td>
                        <span class="badge bg-{{ 'secondary' if tx.type == 'Purchase' else 'success' }}">
                            {{ tx.status }}
                        </span>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="14" class="text-center text-muted py-4">No records found matching your filter criteria.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<script>
function toggleSelectAll(master) {
    const checkboxes = document.querySelectorAll('.tx-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = master.checked;
        handleRowSelect(cb);
    });
}

function handleRowSelect(cb) {
    const row = cb.closest('tr');
    if (cb.checked) {
        row.classList.add('print-selected-row');
    } else {
        row.classList.remove('print-selected-row');
    }
}

function printSelectedVerticalSlips() {
    const selected = document.querySelectorAll('.tx-checkbox:checked');
    if (selected.length === 0) {
        alert('Aapne print karne ke liye koi transaction select nahi ki. Kripya kam se kam 1 check box par click karein.');
        return;
    }

    const container = document.getElementById('verticalSlipsContainer');
    container.innerHTML = '';

    selected.forEach(cb => {
        const row = cb.closest('tr');
        const slipHTML = `
            <div class="vertical-slip">
                <h5>APPLE X - TRANSACTION SLIP</h5>
                <div class="slip-row"><span class="slip-label">1. Date & Time:</span> <span>${row.dataset.datetime}</span></div>
                <div class="slip-row"><span class="slip-label">2. Type:</span> <span>${row.dataset.type}</span></div>
                <div class="slip-row"><span class="slip-label">3. iPhone Model:</span> <span>${row.dataset.model}</span></div>
                <div class="slip-row"><span class="slip-label">4. Storage / Color:</span> <span>${row.dataset.storagecolor}</span></div>
                <div class="slip-row"><span class="slip-label">5. PTA Status:</span> <span>${row.dataset.ptastatus}</span></div>
                <div class="slip-row"><span class="slip-label">6. IMEI:</span> <span>${row.dataset.imei}</span></div>
                <div class="slip-row"><span class="slip-label">7. Qty:</span> <span>${row.dataset.qty}</span></div>
                <div class="slip-row"><span class="slip-label">8. Sale Price:</span> <span>${row.dataset.saleprice}</span></div>
                <div class="slip-row"><span class="slip-label">9. Partner:</span> <span>${row.dataset.partner}</span></div>
                <div class="slip-row"><span class="slip-label">10. Payment Method:</span> <span>${row.dataset.paymentmethod}</span></div>
                <div class="slip-row"><span class="slip-label">11. Status:</span> <span>${row.dataset.status}</span></div>
            </div>
        `;
        container.innerHTML += slipHTML;
    });

    window.print();
    container.innerHTML = '';
}

function handleQuickRange(val) {
    const today = new Date();
    let fromDate = '';
    let toDate = today.toISOString().split('T')[0];

    if (val === 'today') {
        fromDate = toDate;
    } else if (val === 'yesterday') {
        const y = new Date(today);
        y.setDate(today.getDate() - 1);
        fromDate = y.toISOString().split('T')[0];
        toDate = fromDate;
    } else if (val === 'this_week') {
        const firstDay = new Date(today.setDate(today.getDate() - today.getDay()));
        fromDate = firstDay.toISOString().split('T')[0];
        toDate = new Date().toISOString().split('T')[0];
    } else if (val === 'this_month') {
        fromDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
    } else if (val === 'last_month') {
        const firstDay = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastDay = new Date(today.getFullYear(), today.getMonth(), 0);
        fromDate = firstDay.toISOString().split('T')[0];
        toDate = lastDay.toISOString().split('T')[0];
    } else if (val === 'this_year') {
        fromDate = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
    }

    if (fromDate) {
        document.getElementById('date_from').value = fromDate;
        document.getElementById('date_to').value = toDate;
    }
}
</script>
{% endblock %}
"""

def get_template_source(template_name):
    templates = {
        'base': BASE_TEMPLATE,
        'dashboard': DASHBOARD_TEMPLATE,
        'inventory': INVENTORY_TEMPLATE,
        'purchase': PURCHASE_TEMPLATE,
        'sale': SALE_TEMPLATE,
        'reports': REPORTS_TEMPLATE
    }
    if template_name in templates:
        return templates[template_name], template_name, lambda: True
    return None

# ==========================================
# FLASK & DATABASE SETUP
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'apple-x-secure-production-key'
app.jinja_loader = FunctionLoader(get_template_source)

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'data', 'iphone_inventory.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    storage = db.Column(db.String(30), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    pta_status = db.Column(db.String(40), nullable=False, default='PTA Approved')
    condition = db.Column(db.String(40), nullable=False, default='Used')
    sku = db.Column(db.String(100), unique=True, nullable=False)
    stock_qty = db.Column(db.Integer, default=0)
    avg_cost = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    selling_price = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(25), nullable=False)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(25), nullable=False)
    cnic = db.Column(db.String(30), nullable=True)

class IMEI(db.Model):
    __tablename__ = 'imeis'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    imei1 = db.Column(db.String(20), nullable=True)
    battery_health = db.Column(db.Integer, default=100)
    pta_status = db.Column(db.String(40), nullable=False, default='PTA Approved')
    status = db.Column(db.String(30), nullable=False, default='In Stock')
    purchase_cost = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    product = db.relationship('Product', backref=db.backref('imeis', lazy=True))

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    imei1 = db.Column(db.String(20), nullable=True)
    battery_health = db.Column(db.Integer, default=100)
    pta_status = db.Column(db.String(40), nullable=False, default='PTA Approved')
    quantity = db.Column(db.Integer, default=1)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    net_total = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    supplier = db.relationship('Supplier', backref=db.backref('purchases', lazy=True))
    product = db.relationship('Product', backref=db.backref('purchases', lazy=True))

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    imei1 = db.Column(db.String(20), nullable=True)
    pta_status = db.Column(db.String(40), nullable=False, default='PTA Approved')
    quantity = db.Column(db.Integer, default=1)
    selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    cogs = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    gross_profit = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    payment_method = db.Column(db.String(30), nullable=False)
    customer = db.relationship('Customer', backref=db.backref('sales', lazy=True))
    product = db.relationship('Product', backref=db.backref('sales', lazy=True))

# ==========================================
# ROUTES
# ==========================================
@app.route('/health')
def health_check():
    return jsonify({"status": "ok"})

@app.route('/')
def dashboard():
    try:
        search_query = request.args.get('search_imei', '').strip()
        search_result = None
        search_supplier_name = "Unknown"
        search_customer_name = "-"
        search_sold_price = "-"
        search_profit = "-"
        
        if search_query:
            search_result = IMEI.query.filter_by(imei1=search_query).first()
            if search_result:
                purchase_rec = Purchase.query.filter_by(imei1=search_query).first()
                if purchase_rec and purchase_rec.supplier:
                    search_supplier_name = purchase_rec.supplier.name
                    
                if search_result.status == 'Sold':
                    sale_rec = Sale.query.filter_by(imei1=search_query).first()
                    if sale_rec:
                        if sale_rec.customer:
                            search_customer_name = sale_rec.customer.name
                        search_sold_price = f"Rs. {sale_rec.selling_price}"
                        search_profit = f"+Rs. {sale_rec.gross_profit}"

        in_stock_imeis = IMEI.query.filter_by(status='In Stock').all()
        total_inv_value = sum((item.purchase_cost or Decimal('0.00')) for item in in_stock_imeis)
        total_units = len(in_stock_imeis)
        
        purchases_all = Purchase.query.all()
        total_purchase_revenue = sum(p.net_total for p in purchases_all)
        total_units_purchased_count = sum(p.quantity for p in purchases_all)

        sales_all = Sale.query.all()
        total_sales = sum(s.selling_price for s in sales_all)
        total_profit = sum(s.gross_profit for s in sales_all)
        net_pnl = total_profit
        
        recent_purchases = Purchase.query.order_by(Purchase.date.desc()).limit(10).all()
        recent_sales = Sale.query.order_by(Sale.date.desc()).limit(10).all()
        
        return render_template_string(DASHBOARD_TEMPLATE,
                                      active='dashboard',
                                      search_query=search_query,
                                      search_result=search_result,
                                      search_supplier_name=search_supplier_name,
                                      search_customer_name=search_customer_name,
                                      search_sold_price=search_sold_price,
                                      search_profit=search_profit,
                                      total_inv_value=total_inv_value,
                                      total_units=total_units,
                                      total_purchase_revenue=total_purchase_revenue,
                                      total_units_purchased_count=total_units_purchased_count,
                                      total_sales=total_sales,
                                      total_profit=total_profit,
                                      net_pnl=net_pnl,
                                      recent_purchases=recent_purchases,
                                      recent_sales=recent_sales)
    except Exception as e:
        app.logger.exception("Error rendering dashboard")
        return f"An internal error occurred: {e}", 500

@app.route('/inventory')
def inventory_list():
    try:
        raw_imeis = IMEI.query.filter_by(status='In Stock').all()
        inventory_items = []
        for item in raw_imeis:
            supplier_name = "Unknown"
            purchase_rec = Purchase.query.filter_by(imei1=item.imei1).first() if item.imei1 else None
            if purchase_rec and purchase_rec.supplier:
                supplier_name = purchase_rec.supplier.name
            
            inventory_items.append({
                'product': item.product,
                'imei1': item.imei1,
                'battery_health': item.battery_health,
                'pta_status': item.pta_status,
                'purchase_cost': item.purchase_cost,
                'supplier_name': supplier_name
            })

        return render_template_string(INVENTORY_TEMPLATE, active='inventory', inventory_items=inventory_items)
    except Exception as e:
        app.logger.exception("Error rendering inventory")
        return f"An internal error occurred: {e}", 500

@app.route('/purchase', methods=['GET', 'POST'])
def purchase_tab():
    if request.method == 'POST':
        try:
            supplier_name = request.form.get('supplier_name', '').strip()
            supplier_mobile = request.form.get('supplier_mobile', '').strip()
            product_form_id = request.form.get('product_id')
            storage = request.form.get('storage')
            color = request.form.get('color', '').strip()
            pta_status = request.form.get('pta_status', 'PTA Approved')
            imei1 = request.form.get('imei1', '').strip()
            quantity = int(request.form.get('quantity', 1))
            unit_cost = Decimal(request.form.get('unit_cost', '0'))
            battery_health = int(request.form.get('battery_health', 100))
            payment_method = request.form.get('payment_method')
            
            if imei1 and IMEI.query.filter_by(imei1=imei1).first():
                flash('Error: IMEI already exists in database!', 'danger')
                return redirect(url_for('purchase_tab'))
                
            supplier = Supplier.query.filter_by(name=supplier_name).first()
            if not supplier:
                supplier = Supplier(name=supplier_name, mobile=supplier_mobile)
                db.session.add(supplier)
                db.session.commit()
            else:
                supplier.mobile = supplier_mobile
                db.session.commit()
                
            if product_form_id == 'CUSTOM':
                custom_model_name = request.form.get('custom_model', '').strip()
                if not custom_model_name:
                    flash('Error: Please enter a custom iPhone model name!', 'danger')
                    return redirect(url_for('purchase_tab'))
                
                sku_str = f"SKU-CUSTOM-{int(datetime.utcnow().timestamp())}"
                new_prod = Product(
                    model=custom_model_name,
                    storage=storage,
                    color=color,
                    pta_status=pta_status,
                    condition='Used',
                    sku=sku_str,
                    stock_qty=0,
                    avg_cost=Decimal('0.00'),
                    selling_price=Decimal('0.00')
                )
                db.session.add(new_prod)
                db.session.commit()
                product_id = new_prod.id
            else:
                product_id = int(product_form_id)
                prod = Product.query.get(product_id)
                if prod:
                    prod.storage = storage
                    prod.color = color
                    prod.pta_status = pta_status
                    db.session.commit()
                
            net_total = unit_cost * quantity
            purchase = Purchase(
                supplier_id=supplier.id,
                product_id=product_id,
                imei1=imei1 if imei1 else None,
                battery_health=battery_health,
                pta_status=pta_status,
                quantity=quantity,
                unit_cost=unit_cost,
                net_total=net_total,
                payment_method=payment_method
            )
            db.session.add(purchase)
            
            for i in range(quantity):
                unit_imei = imei1 if (quantity == 1 and imei1) else f"AUTO-{int(datetime.utcnow().timestamp())}-{i+1}"
                imei_entry = IMEI(
                    product_id=product_id,
                    imei1=unit_imei,
                    battery_health=battery_health,
                    pta_status=pta_status,
                    status='In Stock',
                    purchase_cost=unit_cost
                )
                db.session.add(imei_entry)
            
            prod = Product.query.get(product_id)
            current_total_val = prod.stock_qty * prod.avg_cost
            prod.stock_qty += quantity
            prod.avg_cost = (current_total_val + net_total) / prod.stock_qty
            
            db.session.commit()
            flash('Purchase recorded successfully for Apple X!', 'success')
            return redirect(url_for('purchase_tab'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Error processing purchase")
            flash(f'An error occurred while saving purchase: {e}', 'danger')
            return redirect(url_for('purchase_tab'))
        
    products = Product.query.all()
    purchases = Purchase.query.order_by(Purchase.date.desc()).all()
    return render_template_string(PURCHASE_TEMPLATE, active='purchase', products=products, purchases=purchases)

@app.route('/sale', methods=['GET', 'POST'])
def sale_tab():
    if request.method == 'POST':
        try:
            customer_name = request.form.get('customer_name', '').strip()
            customer_mobile = request.form.get('customer_mobile', '').strip()
            payment_method = request.form.get('payment_method')
            
            customer = Customer.query.filter_by(mobile=customer_mobile).first()
            if not customer:
                customer = Customer(name=customer_name, mobile=customer_mobile)
                db.session.add(customer)
                db.session.commit()
            else:
                customer.name = customer_name
                db.session.commit()

            # Parse multi-item cart submission dynamically
            form_data = request.form
            item_indices = set()
            for key in form_data.keys():
                if key.startswith('items-') and '-group_key' in key:
                    idx = key.split('-')[1]
                    item_indices.add(idx)

            if not item_indices:
                flash('Error: No items added to the sale cart!', 'danger')
                return redirect(url_for('sale_tab'))

            for idx in item_indices:
                group_key = form_data.get(f'items-{idx}-group_key')
                req_qty = int(form_data.get(f'items-{idx}-quantity', 1))
                unit_selling_price = Decimal(form_data.get(f'items-{idx}-selling_price', '0'))
                custom_imei_input = form_data.get(f'items-{idx}-imei_input', '').strip()

                parts = group_key.split('_')
                product_id = int(parts[0])
                pta_status = parts[1]
                purchase_cost = Decimal(parts[2])

                # Fetch available in-stock units matching this group
                available_units = IMEI.query.filter_by(
                    product_id=product_id,
                    pta_status=pta_status,
                    purchase_cost=purchase_cost,
                    status='In Stock'
                ).limit(req_qty).all()

                if len(available_units) < req_qty:
                    flash(f'Error: Not enough units in stock for the requested quantity!', 'danger')
                    return redirect(url_for('sale_tab'))

                # Process each unit requested in this cart line to avoid unique constraint collisions
                for i, imei_obj in enumerate(available_units):
                    if custom_imei_input:
                        final_imei = f"{custom_imei_input}-{i+1}" if req_qty > 1 else custom_imei_input
                    else:
                        final_imei = imei_obj.imei1 if imei_obj.imei1 else f"AUTO-{int(datetime.utcnow().timestamp())}-{i+1}"

                    existing_check = IMEI.query.filter_by(imei1=final_imei).first()
                    if existing_check and existing_check.id != imei_obj.id:
                        final_imei = f"AUTO-{int(datetime.utcnow().timestamp())}-{i+1}"

                    imei_obj.status = 'Sold'
                    imei_obj.imei1 = final_imei

                # Calculate combined financial numbers for this cart entry
                total_cogs = purchase_cost * req_qty
                total_selling_price = unit_selling_price * req_qty
                total_gross_profit = total_selling_price - total_cogs

                # Create a SINGLE unified Sale entry for the whole quantity
                sale = Sale(
                    customer_id=customer.id,
                    product_id=product_id,
                    imei1=custom_imei_input if custom_imei_input and req_qty == 1 else available_units[0].imei1,
                    pta_status=pta_status,
                    quantity=req_qty,
                    selling_price=total_selling_price,
                    cogs=total_cogs,
                    gross_profit=total_gross_profit,
                    payment_method=payment_method
                )
                db.session.add(sale)

                # Deduct stock quantity
                prod = Product.query.get(product_id)
                if prod.stock_qty >= req_qty:
                    prod.stock_qty -= req_qty
                else:
                    prod.stock_qty = 0

            db.session.commit()
            flash('Multi-unit sale completed successfully and inventory auto-corrected!', 'success')
            return redirect(url_for('sale_tab'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Error processing sale")
            flash(f'An error occurred while executing sale: {e}', 'danger')
            return redirect(url_for('sale_tab'))
        
    # Group available in-stock IMEIs by Product, PTA Status, and Purchase Cost
    raw_imeis = IMEI.query.filter_by(status='In Stock').all()
    grouped_dict = {}
    for imei in raw_imeis:
        key = (imei.product_id, imei.pta_status, imei.purchase_cost)
        if key not in grouped_dict:
            grouped_dict[key] = {
                'product_id': imei.product_id,
                'model': imei.product.model if imei.product else 'Unknown',
                'storage': imei.product.storage if imei.product else '',
                'color': imei.product.color if imei.product else '',
                'pta_status': imei.pta_status,
                'purchase_cost': imei.purchase_cost,
                'ids': []
            }
        grouped_dict[key]['ids'].append(imei.id)

    grouped_inventory = list(grouped_dict.values())
    sales = Sale.query.order_by(Sale.date.desc()).all()
    return render_template_string(SALE_TEMPLATE, active='sale', grouped_inventory=grouped_inventory, sales=sales)

@app.route('/reports')
def reports_tab():
    try:
        tx_type = request.args.get('tx_type', 'all')
        model_id_str = request.args.get('model_id', '')
        storage = request.args.get('storage', '')
        partner_name = request.args.get('partner_name', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        quick_range = request.args.get('quick_range', '')
        
        all_products = Product.query.all()
        
        sales_query = Sale.query
        purchases_query = Purchase.query
        
        if model_id_str:
            try:
                m_id = int(model_id_str)
                sales_query = sales_query.filter_by(product_id=m_id)
                purchases_query = purchases_query.filter_by(product_id=m_id)
            except ValueError:
                pass
            
        if storage:
            matching_prod_ids = [p.id for p in Product.query.filter_by(storage=storage).all()]
            sales_query = sales_query.filter(Sale.product_id.in_(matching_prod_ids))
            purchases_query = purchases_query.filter(Purchase.product_id.in_(matching_prod_ids))

        if partner_name:
            matching_cust_ids = [c.id for c in Customer.query.filter(Customer.name.ilike(f"%{partner_name}%")).all()]
            matching_supp_ids = [s.id for s in Supplier.query.filter(Supplier.name.ilike(f"%{partner_name}%")).all()]
            sales_query = sales_query.filter(Sale.customer_id.in_(matching_cust_ids)) if matching_cust_ids else sales_query.filter(False)
            purchases_query = purchases_query.filter(Purchase.supplier_id.in_(matching_supp_ids)) if matching_supp_ids else purchases_query.filter(False)
            
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                sales_query = sales_query.filter(Sale.date >= dt_from)
                purchases_query = purchases_query.filter(Purchase.date >= dt_from)
            except ValueError:
                pass
                
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                sales_query = sales_query.filter(Sale.date < dt_to)
                purchases_query = purchases_query.filter(Purchase.date < dt_to)
            except ValueError:
                pass

        sales_records = sales_query.order_by(Sale.date.desc()).all()
        purchases_records = purchases_query.order_by(Purchase.date.desc()).all()
        
        unified_transactions = []
        
        total_sales_amt = Decimal('0.00')
        total_purchase_amt = Decimal('0.00')
        total_profit = Decimal('0.00')
        total_units_sold = 0
        total_units_purchased = 0
        
        if tx_type in ['all', 'sales']:
            for s in sales_records:
                total_sales_amt += s.selling_price
                total_profit += s.gross_profit
                total_units_sold += s.quantity
                prod_model = s.product.model if s.product else 'Unknown'
                prod_storage = s.product.storage if s.product else '-'
                prod_color = s.product.color if s.product else '-'
                cust_name = s.customer.name if s.customer else 'Unknown'
                unified_transactions.append({
                    'date': s.date,
                    'type': 'Sale',
                    'model': prod_model,
                    'storage': prod_storage,
                    'color': prod_color,
                    'pta_status': s.pta_status,
                    'imei': s.imei1,
                    'qty': s.quantity,
                    'purchase_price': s.cogs,
                    'sale_price': s.selling_price,
                    'profit': s.gross_profit,
                    'partner': cust_name,
                    'payment_method': s.payment_method,
                    'status': 'Sold'
                })
                
        if tx_type in ['all', 'purchases']:
            for p in purchases_records:
                total_purchase_amt += p.net_total
                total_units_purchased += p.quantity
                imei_status = 'In Stock'
                if p.imei1:
                    imei_obj = IMEI.query.filter_by(imei1=p.imei1).first()
                    if imei_obj:
                        imei_status = imei_obj.status
                    
                prod_model = p.product.model if p.product else 'Unknown'
                prod_storage = p.product.storage if p.product else '-'
                prod_color = p.product.color if p.product else '-'
                supp_name = p.supplier.name if p.supplier else 'Unknown'
                unified_transactions.append({
                    'date': p.date,
                    'type': 'Purchase',
                    'model': prod_model,
                    'storage': prod_storage,
                    'color': prod_color,
                    'pta_status': p.pta_status,
                    'imei': p.imei1,
                    'qty': p.quantity,
                    'purchase_price': p.net_total,
                    'sale_price': '-',
                    'profit': '-',
                    'partner': supp_name,
                    'payment_method': p.payment_method,
                    'status': imei_status
                })
                
        unified_transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template_string(REPORTS_TEMPLATE,
                                      active='reports',
                                      all_products=all_products,
                                      tx_type=tx_type,
                                      quick_range=quick_range,
                                      model_id=model_id_str,
                                      storage=storage,
                                      partner_name=partner_name,
                                      date_from=date_from,
                                      date_to=date_to,
                                      total_sales_amt=total_sales_amt,
                                      total_purchase_amt=total_purchase_amt,
                                      total_profit=total_profit,
                                      total_units_sold=total_units_sold,
                                      total_units_purchased=total_units_purchased,
                                      unified_transactions=unified_transactions)
    except Exception as e:
        app.logger.exception("Error generating reports dashboard")
        return f"An internal server error occurred while loading reports: {e}", 500

@app.route('/reports/export/csv')
def export_csv():
    try:
        tx_type = request.args.get('tx_type', 'all')
        model_id_str = request.args.get('model_id', '')
        storage = request.args.get('storage', '')
        partner_name = request.args.get('partner_name', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        sales_query = Sale.query
        purchases_query = Purchase.query
        
        if model_id_str:
            try:
                m_id = int(model_id_str)
                sales_query = sales_query.filter_by(product_id=m_id)
                purchases_query = purchases_query.filter_by(product_id=m_id)
            except ValueError:
                pass
            
        if storage:
            matching_prod_ids = [p.id for p in Product.query.filter_by(storage=storage).all()]
            sales_query = sales_query.filter(Sale.product_id.in_(matching_prod_ids))
            purchases_query = purchases_query.filter(Purchase.product_id.in_(matching_prod_ids))

        if partner_name:
            matching_cust_ids = [c.id for c in Customer.query.filter(Customer.name.ilike(f"%{partner_name}%")).all()]
            matching_supp_ids = [s.id for s in Supplier.query.filter(Supplier.name.ilike(f"%{partner_name}%")).all()]
            sales_query = sales_query.filter(Sale.customer_id.in_(matching_cust_ids)) if matching_cust_ids else sales_query.filter(False)
            purchases_query = purchases_query.filter(Purchase.supplier_id.in_(matching_supp_ids)) if matching_supp_ids else purchases_query.filter(False)
            
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                sales_query = sales_query.filter(Sale.date >= dt_from)
                purchases_query = purchases_query.filter(Purchase.date >= dt_from)
            except ValueError:
                pass
                
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                sales_query = sales_query.filter(Sale.date < dt_to)
                purchases_query = purchases_query.filter(Purchase.date < dt_to)
            except ValueError:
                pass

        sales_records = sales_query.all()
        purchases_records = purchases_query.all()
        
        si = io.StringIO()
        cw = csv.writer(si)
        
        cw.writerow(['Date & Time', 'Type', 'Model', 'Storage', 'Color', 'PTA Status', 'IMEI', 'Qty', 'Purchase Price', 'Sale Price', 'Profit/Loss', 'Partner', 'Payment Method', 'Status'])
        
        if tx_type in ['all', 'sales']:
            for s in sales_records:
                cw.writerow([
                    s.date.strftime('%Y-%m-%d %H:%M'),
                    'Sale',
                    s.product.model if s.product else 'Unknown',
                    s.product.storage if s.product else '',
                    s.product.color if s.product else '',
                    s.pta_status,
                    s.imei1,
                    s.quantity,
                    s.cogs,
                    s.selling_price,
                    s.gross_profit,
                    s.customer.name if s.customer else 'Unknown',
                    s.payment_method,
                    'Sold'
                ])
                
        if tx_type in ['all', 'purchases']:
            for p in purchases_records:
                imei_status = 'In Stock'
                if p.imei1:
                    imei_obj = IMEI.query.filter_by(imei1=p.imei1).first()
                    if imei_obj:
                        imei_status = imei_obj.status
                    
                cw.writerow([
                    p.date.strftime('%Y-%m-%d %H:%M'),
                    'Purchase',
                    p.product.model if p.product else 'Unknown',
                    p.product.storage if p.product else '',
                    p.product.color if p.product else '',
                    p.pta_status,
                    p.imei1,
                    p.quantity,
                    p.net_total,
                    '',
                    '',
                    p.supplier.name if p.supplier else 'Unknown',
                    p.payment_method,
                    imei_status
                ])
                
        output = si.getvalue()
        si.close()
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=apple_x_report.csv"}
        )
    except Exception as e:
        app.logger.exception("Error exporting CSV report")
        return f"Error generating CSV export: {e}", 500

# ==========================================
# SEED INITIAL DATA (IPHONE 5 TO 18)
# ==========================================
def generate_default_models():
    models = []
    base_series = [
        "iPhone 5", "iPhone 5s", "iPhone 6", "iPhone 6 Plus", "iPhone 6s", "iPhone 6s Plus",
        "iPhone SE (1st Gen)", "iPhone 7", "iPhone 7 Plus", "iPhone 8", "iPhone 8 Plus", "iPhone X",
        "iPhone XR", "iPhone XS", "iPhone XS Max", "iPhone 11", "iPhone 11 Pro", "iPhone 11 Pro Max",
        "iPhone SE (2nd Gen)", "iPhone 12 mini", "iPhone 12", "iPhone 12 Pro", "iPhone 12 Pro Max",
        "iPhone 13 mini", "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max", "iPhone SE (3rd Gen)",
        "iPhone 14", "iPhone 14 Plus", "iPhone 14 Pro", "iPhone 14 Pro Max",
        "iPhone 15", "iPhone 15 Plus", "iPhone 15 Pro", "iPhone 15 Pro Max",
        "iPhone 16", "iPhone 16 Plus", "iPhone 16 Pro", "iPhone 16 Pro Max",
        "iPhone 17", "iPhone 17 Slim", "iPhone 17 Pro", "iPhone 17 Pro Max",
        "iPhone 18", "iPhone 18 Pro", "iPhone 18 Pro Max"
    ]
    for m in base_series:
        models.append({"model": m})
    return models

# ==========================================
# DATABASE INITIALIZATION & MIGRATIONS
# ==========================================
with app.app_context():

    # Create any missing tables
    db.create_all()

    # Add PTA columns to older databases if missing
    with db.engine.connect() as conn:
        for table, col, col_type in [
            ('imeis', 'pta_status', "VARCHAR(40) DEFAULT 'PTA Approved'"),
            ('purchases', 'pta_status', "VARCHAR(40) DEFAULT 'PTA Approved'"),
            ('sales', 'pta_status', "VARCHAR(40) DEFAULT 'PTA Approved'")
        ]:
            try:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                )
                conn.commit()
            except Exception:
                conn.rollback()

    # Make purchases.imei1 nullable in existing SQLite databases
    with db.engine.begin() as conn:

        columns = conn.exec_driver_sql(
            "PRAGMA table_info(purchases)"
        ).fetchall()

        imei_column = next(
            (col for col in columns if col[1] == 'imei1'),
            None
        )

        # SQLite PRAGMA: column index 3 indicates NOT NULL
        if imei_column and imei_column[3] == 1:

            conn.exec_driver_sql("""
                CREATE TABLE purchases_new (
                    id INTEGER PRIMARY KEY,
                    date DATETIME,
                    supplier_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    imei1 VARCHAR(20) NULL,
                    battery_health INTEGER,
                    pta_status VARCHAR(40) NOT NULL DEFAULT 'PTA Approved',
                    quantity INTEGER,
                    unit_cost NUMERIC(12, 2) NOT NULL,
                    net_total NUMERIC(12, 2) NOT NULL,
                    payment_method VARCHAR(30) NOT NULL,
                    FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
            """)

            conn.exec_driver_sql("""
                INSERT INTO purchases_new (
                    id, date, supplier_id, product_id, imei1,
                    battery_health, pta_status, quantity,
                    unit_cost, net_total, payment_method
                )
                SELECT
                    id, date, supplier_id, product_id, imei1,
                    battery_health, pta_status, quantity,
                    unit_cost, net_total, payment_method
                FROM purchases
            """)

            conn.exec_driver_sql("DROP TABLE purchases")

            conn.exec_driver_sql("""
                ALTER TABLE purchases_new RENAME TO purchases
            """)

    # Seed default iPhone models if database is empty
    if Product.query.count() == 0:

        for item in generate_default_models():

            p = Product(
                model=item["model"],
                storage="128GB",
                color="Space Gray",
                pta_status="PTA Approved",
                condition="Used",
                sku=f"SKU-{item['model'].replace(' ', '-').upper()}",
                stock_qty=0,
                avg_cost=Decimal('0.00'),
                selling_price=Decimal('0.00')
            )

            db.session.add(p)

        db.session.commit()


# ==========================================
# RUN APPLICATION
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)