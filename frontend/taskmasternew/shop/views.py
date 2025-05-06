from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView, View
from .models import Category, Product, Order, OrderItem, ShippingAddress
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.db.models import Sum
from django.urls import reverse
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from .forms import CategoryForm, ProductForm, OrderForm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from datetime import datetime

# Create your views here.

class ProductListView(ListView):
    model = Product
    template_name = 'shop/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            self.category = get_object_or_404(Category, slug=category_slug)
            queryset = queryset.filter(category=self.category)
        else:
            self.category = None
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['category'] = self.category
        return context

class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_detail.html'
    context_object_name = 'product'
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    
    # Convert product_id to string since session stores keys as strings
    product_id = str(product_id)
    
    if product_id in cart:
        cart[product_id]['quantity'] += 1
    else:
        cart[product_id] = {
            'name': product.name,
            'price': str(product.price),
            'quantity': 1,
            'image': product.image.url if product.image else None
        }
    
    request.session['cart'] = cart
    messages.success(request, f'{product.name} added to your cart.')
    return redirect('shop:cart_detail')

@login_required
def cart_detail(request):
    cart = request.session.get('cart', {})
    cart_items = []
    subtotal = Decimal('0.00')
    shipping_cost = Decimal('20.00')
    tax_rate = Decimal('0.18')
    
    for product_id, item in cart.items():
        product = get_object_or_404(Product, id=product_id)
        item_total = Decimal(str(item['price'])) * Decimal(str(item['quantity']))
        cart_items.append({
            'product': product,
            'quantity': item['quantity'],
            'total': item_total
        })
        subtotal += item_total
    
    tax = subtotal * tax_rate
    total = subtotal + shipping_cost + tax
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax': tax,
        'total': total
    }
    return render(request, 'shop/cart_detail.html', context)

@login_required
def update_cart_quantity(request, product_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        product_id = str(product_id)
        quantity = int(request.POST.get('quantity', 1))
        
        if product_id in cart:
            if quantity > 0:
                cart[product_id]['quantity'] = quantity
            else:
                del cart[product_id]
            
            request.session['cart'] = cart
            messages.success(request, 'Cart updated successfully.')
        else:
            messages.error(request, 'Product not found in cart.')
    
    return redirect('shop:cart_detail')

@login_required
def remove_from_cart(request, product_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        product_id = str(product_id)
        
        if product_id in cart:
            del cart[product_id]
            request.session['cart'] = cart
            messages.success(request, 'Item removed from cart.')
        else:
            messages.error(request, 'Product not found in cart.')
    
    return redirect('shop:cart_detail')

class UserProfileView(LoginRequiredMixin, View):
    template_name = 'shop/profile.html'

    def get(self, request):
        user = request.user
        orders = Order.objects.filter(user=user).order_by('-created_at')
        
        # Calculate statistics
        total_orders = orders.count()
        completed_orders = orders.filter(status='completed').count()
        pending_orders = orders.filter(status='pending').count()
        total_spent = orders.filter(status='completed').aggregate(
            total=Sum('total')
        )['total'] or 0

        context = {
            'user': user,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'pending_orders': pending_orders,
            'total_spent': total_spent,
            'orders': orders,
        }
        return render(request, self.template_name, context)

class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'shop/order_detail.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        # Ensure users can only view their own orders
        return Order.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        
        # Add order items to context
        context['order_items'] = order.items.all()
        
        # Add shipping address to context
        context['shipping_address'] = {
            'full_name': f"{order.first_name} {order.last_name}",
            'address': order.shipping_address,
            'phone': order.phone,
            'email': order.email
        }
        
        # Add order totals to context
        context['subtotal'] = order.subtotal
        context['shipping_cost'] = order.shipping_cost
        context['tax'] = order.tax
        context['total'] = order.total
        
        return context

@login_required
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('shop:cart_detail')
    
    # Get user's saved addresses
    saved_addresses = ShippingAddress.objects.filter(user=request.user)
    default_address = saved_addresses.filter(is_default=True).first()
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        city = request.POST.get('city')
        pin_code = request.POST.get('pin_code')
        payment_method = request.POST.get('payment_method')
        save_address = request.POST.get('save_address') == 'on'
        make_default = request.POST.get('make_default') == 'on'

        # Save the address if requested
        if save_address:
            shipping_address = ShippingAddress.objects.create(
                user=request.user,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                pin_code=pin_code,
                is_default=make_default
            )

        # Calculate order totals
        subtotal = Decimal('0.00')
        shipping_cost = Decimal('20.00')  # Fixed shipping cost
        tax_rate = Decimal('0.18')  # 18% tax

        # Create order
        order = Order.objects.create(
            user=request.user,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            shipping_address=f"{address}, {city}, {pin_code}",
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax=Decimal('0.00'),
            total=Decimal('0.00')
        )

        # Add order items
        for product_id, item in cart.items():
            product = get_object_or_404(Product, id=product_id)
            price = Decimal(str(item['price']))
            quantity = int(item['quantity'])
            item_total = price * Decimal(str(quantity))
            subtotal += item_total

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price
            )

        # Update order totals
        tax = subtotal * tax_rate
        total = subtotal + shipping_cost + tax

        order.subtotal = subtotal
        order.tax = tax
        order.total = total
        order.save()

        # Clear cart
        request.session['cart'] = {}

        # Redirect to order confirmation
        return redirect('shop:order_confirmation', order_id=order.id)

    # Get cart items for display
    cart_items = []
    subtotal = Decimal('0.00')
    shipping_cost = Decimal('20.00')
    tax_rate = Decimal('0.18')

    for product_id, item in cart.items():
        product = get_object_or_404(Product, id=product_id)
        price = Decimal(str(item['price']))
        quantity = int(item['quantity'])
        item_total = price * Decimal(str(quantity))
        subtotal += item_total
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'total': item_total
        })

    tax = subtotal * tax_rate
    total = subtotal + shipping_cost + tax

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax': tax,
        'total': total,
        'saved_addresses': saved_addresses,
        'default_address': default_address
    }
    return render(request, 'shop/checkout.html', context)

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Parse the shipping address string into components
    address_parts = order.shipping_address.split(', ')
    street_address = address_parts[0] if len(address_parts) > 0 else ''
    city = address_parts[1] if len(address_parts) > 1 else ''
    state_zip = address_parts[2] if len(address_parts) > 2 else ''
    
    # Split state and zip if they exist
    state = ''
    zip_code = ''
    if state_zip:
        state_zip_parts = state_zip.split(' ')
        state = state_zip_parts[0] if len(state_zip_parts) > 0 else ''
        zip_code = state_zip_parts[1] if len(state_zip_parts) > 1 else ''
    
    context = {
        'order': order,
        'shipping_address': {
            'full_name': f"{order.first_name} {order.last_name}",
            'street_address': street_address,
            'city': city,
            'state': state,
            'zip': zip_code,
            'phone': order.phone,
            'email': order.email
        }
    }
    return render(request, 'shop/order_confirmation.html', context)

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Only allow cancellation of pending orders
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Order #{order.id} has been cancelled.')
    else:
        messages.error(request, 'This order cannot be cancelled.')
    
    return redirect('shop:user_profile')

@login_required
def get_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    data = {
        'first_name': address.first_name,
        'last_name': address.last_name,
        'email': address.email,
        'phone': address.phone,
        'address': address.address,
        'city': address.city,
        'pin_code': address.pin_code
    }
    return JsonResponse(data)

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@user_passes_test(is_admin, login_url='login')
def admin_categories(request):
    categories = Category.objects.all().order_by('name')
    context = {
        'categories': categories,
        'admin_title': 'Categories Management',
    }
    return render(request, 'admin/categories.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_products(request):
    products = Product.objects.filter(is_active=True).order_by('-created_at')
    categories = Category.objects.all()
    
    # Apply filters if provided
    category_filter = request.GET.get('category')
    if category_filter and category_filter != 'all':
        products = products.filter(category_id=category_filter)
    
    context = {
        'products': products,
        'categories': categories,
        'category_filter': category_filter,
        'admin_title': 'Products Management',
    }
    return render(request, 'admin/products.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_orders(request):
    orders = Order.objects.all().order_by('-created_at')
    
    # Apply filters if provided
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    context = {
        'orders': orders,
        'order_statuses': Order.STATUS_CHOICES,
        'status_filter': status_filter,
        'admin_title': 'Orders Management',
    }
    return render(request, 'admin/orders.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully.')
            return redirect('shop:admin_categories')
    else:
        form = CategoryForm()
    
    context = {
        'form': form,
        'admin_title': 'Add New Category',
    }
    return render(request, 'admin/category_form.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('shop:admin_categories')
    else:
        form = CategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
        'admin_title': 'Edit Category',
    }
    return render(request, 'admin/category_form.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully.')
        return redirect('shop:admin_categories')
    
    context = {
        'category': category,
        'admin_title': 'Delete Category',
    }
    return render(request, 'admin/category_confirm_delete.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" added successfully.')
            return redirect('shop:admin_products')
    else:
        form = ProductForm()

    context = {
        'admin_title': 'Add New Product',
        'form': form,
    }
    return render(request, 'admin/product_form.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" updated successfully.')
            return redirect('shop:admin_products')
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'admin_title': 'Edit Product',
    }
    return render(request, 'admin/product_form.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.delete()
        messages.success(request, f'Product "{product.name}" deleted successfully.')
        return redirect('shop:admin_products')
    
    context = {
        'product': product,
        'admin_title': 'Delete Product',
    }
    return render(request, 'admin/product_confirm_delete.html', context)

@user_passes_test(lambda u: u.is_superuser)
def admin_order_edit(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Order updated successfully.')
            return redirect('shop:admin_orders')
    else:
        form = OrderForm(instance=order)
    
    context = {
        'admin_title': 'Edit Order',
        'form': form,
        'order': order,
    }
    return render(request, 'admin/order_form.html', context)

@user_passes_test(lambda u: u.is_superuser)
def admin_order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Order deleted successfully.')
        return redirect('shop:admin_orders')
    
    context = {
        'admin_title': 'Delete Order',
        'order': order,
    }
    return render(request, 'admin/order_confirm_delete.html', context)

def generate_order_receipt(order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#1E3A8A')  # Dark blue color
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=10,
        alignment=1,
        textColor=colors.HexColor('#4B5563')  # Gray color
    )
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        spaceBefore=20,
        alignment=1,
        textColor=colors.HexColor('#6B7280')  # Light gray color
    )

    # Company Header with Logo Placeholder
    elements.append(Paragraph("TASKMASTER", title_style))
    elements.append(Paragraph("123 Business Street, City, State 12345", header_style))
    elements.append(Paragraph("Phone: (123) 456-7890 | Email: info@taskmaster.com", header_style))
    elements.append(Paragraph("www.taskmaster.com | GSTIN: 29ABCDE1234F1Z5", header_style))
    elements.append(Paragraph("----------------------------------------", header_style))
    elements.append(Spacer(1, 20))

    # Receipt Title with Transaction Details
    elements.append(Paragraph(f"TAX INVOICE #{order.id}", title_style))
    elements.append(Paragraph(f"Date: {order.created_at.strftime('%B %d, %Y %I:%M %p')}", header_style))
    elements.append(Spacer(1, 20))

    # Customer Information with Billing Details
    elements.append(Paragraph("BILLING INFORMATION", styles['Heading2']))
    elements.append(Spacer(1, 10))

    customer_info = [
        ["Customer Name:", f"{order.first_name} {order.last_name}"],
        ["Email:", order.email],
        ["Phone:", order.phone],
        ["Payment Method:", order.get_payment_method_display()],
    ]
    
    customer_table = Table(customer_info, colWidths=[150, 350])
    customer_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F4F6')),  # Light gray background
        ('PADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1E3A8A')),  # Dark blue text
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 20))

    # Shipping Address with Additional Details
    elements.append(Paragraph("SHIPPING INFORMATION", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    shipping_info = [
        ["Shipping Address:", order.shipping_address],
        ["Expected Delivery:", (order.created_at + timezone.timedelta(days=3)).strftime("%B %d, %Y")],
        ["Shipping Method:", "Standard Delivery"],
        ["Tracking Number:", f"TRK{order.id}{order.created_at.strftime('%Y%m%d')}"],
    ]
    
    shipping_table = Table(shipping_info, colWidths=[150, 350])
    shipping_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F4F6')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1E3A8A')),
    ]))
    elements.append(shipping_table)
    elements.append(Spacer(1, 20))

    # Order Items with Product Details
    elements.append(Paragraph("PRODUCT DETAILS", styles['Heading2']))
    elements.append(Spacer(1, 10))

    # Table header
    items_data = [["Product", "Unit Price", "Qty", "Tax", "Total"]]
    
    # Add order items
    for item in order.items.all():
        item_tax = (item.price * item.quantity) * Decimal('0.18')  # 18% tax
        items_data.append([
            item.product.name,
            f"${item.price:.2f}",
            str(item.quantity),
            f"${item_tax:.2f}",
            f"${(item.price * item.quantity + item_tax):.2f}"
        ])

    # Add order totals with tax breakdown
    items_data.extend([
        ["", "", "", "Subtotal:", f"${order.subtotal:.2f}"],
        ["", "", "", "Shipping:", f"${order.shipping_cost:.2f}"],
        ["", "", "", "Tax (18%):", f"${order.tax:.2f}"],
        ["", "", "", "Total:", f"${order.total:.2f}"]
    ])

    items_table = Table(items_data, colWidths=[200, 80, 60, 80, 100])
    items_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -4), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -4), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, -4), (-1, -1), colors.HexColor('#1E3A8A')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 20))

    # Thank you message and Terms
    elements.append(Paragraph("Thank you for your purchase!", header_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Please keep this invoice for your records.", header_style))
    elements.append(Spacer(1, 20))

    # Footer with Terms and Conditions
    elements.append(Paragraph("----------------------------------------", header_style))
    elements.append(Paragraph("TERMS AND CONDITIONS", footer_style))
    elements.append(Paragraph("1. This is a computer-generated invoice and does not require a signature.", footer_style))
    elements.append(Paragraph("2. Goods once sold will not be taken back or exchanged.", footer_style))
    elements.append(Paragraph("3. For any queries, please contact our customer service.", footer_style))
    elements.append(Paragraph("4. All prices are inclusive of taxes.", footer_style))
    elements.append(Paragraph("5. Warranty terms and conditions apply as per manufacturer's policy.", footer_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Thank you for shopping with us!", footer_style))
    elements.append(Paragraph("© 2024 TASKMASTER. All rights reserved.", footer_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

@login_required
def download_order_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    buffer = generate_order_receipt(order)
    
    # Create the HttpResponse object with the appropriate PDF headers
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="order_receipt_{order.id}.pdf"'
    return response
