# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, LoginForm, CattleForm, FinancialForm
from .models import Cattle, FinancialRecord, InventoryItem
from django.db.models import Sum
# core/views.py
from .models import InventoryItem, InventoryHistory
from .forms import InventoryItemForm, StockUpdateForm


def home(request):
    return render(request, 'core/home.html')

def register(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.is_doctor:
                return redirect('doctor_dashboard')
            else:
                return redirect('farmer_dashboard')
    else:
        form = SignUpForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Debugging: Check user type and redirect
            if user.is_doctor:
                return redirect('doctor_dashboard')
            elif user.is_farmer:
                return redirect('farmer_dashboard')
            else:
                # Fallback for superusers or users without a type
                return redirect('farmer_dashboard') 
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})

@login_required
def farmer_dashboard(request):
    return render(request, 'core/farmer_dashboard.html')

@login_required
def doctor_dashboard(request):
    return render(request, 'core/doctor_dashboard.html')

@login_required
def manage_cattle(request):
    if request.method == 'POST':
        form = CattleForm(request.POST)
        if form.is_valid():
            cattle = form.save(commit=False)
            cattle.owner = request.user
            cattle.save()
            return redirect('manage_cattle')
    else:
        form = CattleForm()
    cattle_list = Cattle.objects.filter(owner=request.user)
    return render(request, 'core/manage_cattle.html', {'cattle_list': cattle_list, 'form': form})

@login_required
def performance(request):
    if request.method == 'POST':
        form = FinancialForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.save()
            return redirect('performance')
    else:
        form = FinancialForm()
    records = FinancialRecord.objects.filter(user=request.user).order_by('-date')
    total_income = records.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = records.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense
    return render(request, 'core/performance.html', {
        'records': records, 'form': form,
        'total_income': total_income, 'total_expense': total_expense, 'net_profit': net_profit
    })


@login_required
def inventory(request):
    """View current stock, days remaining, and add new items"""
    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            # Create initial history log
            InventoryHistory.objects.create(
                item=item, action='ADD', quantity_changed=item.quantity, notes="Initial Stock"
            )
            return redirect('inventory')
    else:
        form = InventoryItemForm()
        
    items = InventoryItem.objects.filter(user=request.user)
    return render(request, 'core/inventory.html', {'items': items, 'form': form})

@login_required
def update_inventory(request, pk):
    """Handle Adding or Consuming stock with History"""
    item = get_object_or_404(InventoryItem, pk=pk, user=request.user)
    history = item.history.all().order_by('-date')[:10]  # Show last 10 logs

    if request.method == 'POST':
        form = StockUpdateForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            qty = form.cleaned_data['quantity']
            notes = form.cleaned_data['notes']

            # Update the main item quantity
            if action == 'ADD':
                item.quantity += qty
            elif action == 'CONSUME':
                if item.quantity >= qty:
                    item.quantity -= qty
                else:
                    form.add_error('quantity', 'Not enough stock to consume this amount!')
                    return render(request, 'core/update_inventory.html', {'form': form, 'item': item, 'history': history})

            item.save()

            # Create History Record
            InventoryHistory.objects.create(
                item=item, action=action, quantity_changed=qty, notes=notes
            )
            return redirect('inventory')
    else:
        form = StockUpdateForm()

    return render(request, 'core/update_inventory.html', {'form': form, 'item': item, 'history': history})

# --- Append to core/views.py ---
from .models import Message, User
from .forms import MessageForm
from django.db.models import Q

@login_required
def doctor_list(request):
    """List all registered doctors for the farmer to contact"""
    doctors = User.objects.filter(is_doctor=True)
    return render(request, 'core/doctor_list.html', {'doctors': doctors})

@login_required
def chat_view(request, user_id):
    """Chat room between current user and another user (user_id)"""
    other_user = get_object_or_404(User, pk=user_id)
    
    # Fetch conversation history
    messages = Message.objects.filter(
        (Q(sender=request.user) & Q(recipient=other_user)) |
        (Q(sender=other_user) & Q(recipient=request.user))
    ).order_by('timestamp')

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.recipient = other_user
            message.save()
            return redirect('chat_view', user_id=user_id)
    else:
        form = MessageForm()

    return render(request, 'core/chat.html', {
        'other_user': other_user, 
        'messages': messages, 
        'form': form
    })

@login_required
def inbox(request):
    """List of people who have exchanged messages with the current user"""
    # Get all unique users involved in messages with me
    sent_to = Message.objects.filter(sender=request.user).values_list('recipient', flat=True)
    received_from = Message.objects.filter(recipient=request.user).values_list('sender', flat=True)
    
    contact_ids = set(list(sent_to) + list(received_from))
    contacts = User.objects.filter(id__in=contact_ids)
    
    return render(request, 'core/inbox.html', {'contacts': contacts})
