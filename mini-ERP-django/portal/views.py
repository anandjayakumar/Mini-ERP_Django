# coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import update_last_login
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
#from django.contrib.auth.models import User
from django.template import Context, Template, RequestContext
from django.template.loader import get_template
from django.forms.models import inlineformset_factory
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView
from django.db import transaction
from django.db.models import Sum
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from minierp import settings
from portal.forms import *
from portal.models import *

from decimal import Decimal
import datetime, random, json, requests
from taggit.models import Tag
import yaml
import logging, re
from urllib.parse import quote_plus


# @login_required - If the user isn’t logged in, redirect to settings.LOGIN_URL,
# passing the current absolute path in the query string.

# ----------------------------------------------------------------
#                 Global Settings Variables
# ----------------------------------------------------------------

add_to_limit = Decimal('5000')
rootEntry = 'E000000000000'
company_lvl1_entry = 'E000000000010'
exclude_list = {'E000000000001', 'E000000000003', 'E000000000004', }
rchg_service_charge=Decimal('5')


# ----------------------------------------------------------------
#                      General Pages
# ----------------------------------------------------------------

# Home Page

def index(request):
    if request.user.is_authenticated():
            user_cat = request.user.username[:1]
            print (user_cat)
            update_last_login(None, request.user)
            if user_cat == 'C':
                if tncaccept(request.user):
                    customer = Customer.objects.get(user=request.user)
                    name = customer.user.name
                    orders = Entry.objects.filter(customer_id=request.user.username).values('bill_id')
                    order_count = orders.count()
                    balance = customer.account_balance
                    recharge = Recharge.objects.filter(customer_id = request.user.username,success=True).aggregate(Sum('amount'))['amount__sum']
                    return render(request, 'customer/customerdash.html', {'name':name,'order_count':order_count, 'balance':balance, 'recharge':recharge})
                else:
                    return HttpResponseRedirect('/termsandconditions/')

            elif user_cat == 'F':
                orders = Entry.objects.filter(seller_id=request.user.username).values('bill_id')
                order_count = orders.count()
                product_count = Stock.objects.all().filter(user_id=request.user.username).count()
                return render(request, 'franchise/franchisedash.html', {'product_count':product_count,'order_count':order_count})

            elif user_cat == 'S':
                return render(request, 'staff/staffdash.html',)

            elif request.user.is_superuser:
                customer_count = Customer.objects.all().count()
                franchise_count = Franchise.objects.all().count()
                order_count = Bill.objects.all().count()
                return render(request, 'admin/admindash.html', {'customer_count':customer_count,'franchise_count':franchise_count,'order_count':order_count})

            else:
                return HttpResponseRedirect('/logout/')
    else:
        return HttpResponseRedirect('/login/')

# Login Page

def login_page(request):
    error = ''
    if request.user.is_authenticated():
        logout(request)
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            mobile_number = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=mobile_number, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    request.session['user_role'] = user.username[:1]
                    return HttpResponseRedirect('/')
                else:
                    return HttpResponseRedirect('/login/')
            else:
                error = "Username & password doesn't match."
        else:
            error = "Validation error."
    else:
        form = LoginForm()
    return render(request, 'common/login.html', {'form': form, 'error': error})


# Profile Page

@login_required
def profile(request):
    if request.user.username.startswith('C'):
        profile = Customer.objects.get(user=request.user)
    elif request.user.username.startswith('F'):
        profile = Franchise.objects.get(user=request.user)
    elif request.user.username.startswith('S'):
        profile = Staff.objects.get(user=request.user)
    else:
        profile = Franchise.objects.get(user__username="F1")
    return render(request, 'common/profile.html', {'user': request.user, 'profile':profile})


# Logout view - not displayed

@login_required
def logout_page(request):
    try:
        del request.session['user_role']
    except:
        pass
    logout(request)
    return HttpResponseRedirect('/')

# Account Registration

def register(request):
    if request.user.is_authenticated():
        logout(request)
    form = RegistrationForm()
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = PgUser.objects.create_user(mobile_number=form.cleaned_data['mobile_number'],username=form.cleaned_data['username'],
                                            password=form.cleaned_data['password1'], email=form.cleaned_data['email'], name=form.cleaned_data['name'])
            return HttpResponseRedirect('/login/?notif_message=Registration successful')
    return render(request, 'common/register.html', {'form': form})


# Account Update

@login_required
def edit_user(request, pk=None):
    user = request.user
    user_form = UserForm(instance=user)
    CustomerInlineFormset = inlineformset_factory(PgUser, Customer, fields=('permanent_address', 'billing_address'),
                                                  can_delete=False)
    formset = CustomerInlineFormset(instance=user)

    # Separate form for both User and Customer
    # Hence they are saved separately
    if request.user.is_authenticated() and request.user.id == user.id:
        if request.method == "POST":
            user_form = UserForm(request.POST, request.FILES, instance=user)
            formset = CustomerInlineFormset(request.POST, request.FILES, instance=user)

            if user_form.is_valid():
                created_user = user_form.save(commit=False)
                formset = CustomerInlineFormset(request.POST, request.FILES, instance=created_user)

                if formset.is_valid():
                    created_user.save()
                    formset.save()
                    return HttpResponseRedirect('/profile/?notif_message=Your profile has been updated.')

        return render(request, "common/account_update.html", {"username": pk, "form": user_form, "formset": formset,})
    else:
        raise PermissionDenied


#Message view

@login_required
def message(request):
    return render(request, "common/message.html")

# ----------------------------------------------------------------
#                      Customer Pages
# ----------------------------------------------------------------


# View Entries

class EntryList(ListView):
    template_name = 'customer/entrylist.html'
    paginate_by = '10'
    context_object_name = 'entry_list'

    def get_queryset(self):
        try:
            name = self.request.GET['search']
        except:
            name = ''
        if (name != ''):
            object_list = Entry.objects.all().filter(customer_id=self.request.user.username).filter(
                entry_id__icontains=name)
        else:
            object_list = Entry.objects.all().filter(customer_id=self.request.user.username).order_by('-entry_id')
        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('C')))
    def dispatch(self, *args, **kwargs):
        return super(EntryList, self).dispatch(*args, **kwargs)


# View each Entry in detail
# Should be made such that user can access only his entries

class EntryDetailView(ListView):
    template_name = 'customer/entrydetail.html'
    paginate_by = '10'
    context_object_name = 'transaction_list'

    def get_queryset(self):
        e_id = self.kwargs['id']
        entry = Entry.objects.get(entry_id=e_id)
        if entry.customer_id == self.request.user.username:
            return Transaction.objects.all().filter(to_id=e_id)

    @method_decorator(user_passes_test(lambda u: u.username.startswith('C')))
    def dispatch(self, *args, **kwargs):
        return super(EntryDetailView, self).dispatch(*args, **kwargs)



# Recharge view
@user_passes_test(lambda u: u.username.startswith('C'))
@transaction.atomic
def services_recharge(request):
    if request.method == 'POST':
        form = RechargeForm(request.POST)
        if form.is_valid():
            customer = Customer.objects.get(user__username=request.user.username)
            curr_balance = customer.account_balance
            data = form.cleaned_data
            amt = int(data['amount'])
            if amt + rchg_service_charge > curr_balance :
                return HttpResponseRedirect('/message?message=Your account balance is insufficient.')
            new_amt = curr_balance - amt - rchg_service_charge
            customer.account_balance = new_amt
            customer.save()
            rc = Recharge()
            number = data['number'].replace(",","")
            code = Operator.objects.get(name=data['operator']).code
            rc.operator_code = code
            rc.amount = amt
            rc.number = number
            rc.customer_id = request.user.username
            rc.save()
            token,status=rechargeAPI(rc,customer)
            print("token = ",token)
            if status==0:
                customer.account_balance = curr_balance
                customer.save()
            return HttpResponseRedirect('/message?message=Your request has been submitted. It will be processed shortly.')
    else:
        form = RechargeForm()
    return render(request, 'customer/recharge.html', {'form': form})


# View Recharge History

class services_rechargehistory(ListView):
    template_name = 'customer/rechargehistory.html'
    paginate_by = '10'
    context_object_name = 'recharge_list'

    def get_queryset(self):
        try:
            name = self.request.GET['search']
        except:
            name = ''
        if (name != ''):
            object_list = Recharge.objects.all().filter(customer_id=self.request.user.username).filter(
                number__icontains=name)
        else:
            object_list = Recharge.objects.all().filter(customer_id=self.request.user.username).order_by('-recharge_id')

        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('C')))
    def dispatch(self, *args, **kwargs):
        return super(services_rechargehistory, self).dispatch(*args, **kwargs)

# ----------------------------------------------------------------
#                      Franchise Pages
# ----------------------------------------------------------------

# View Bills List

class BillsList(ListView):
    template_name = 'franchise/billslist.html'
    paginate_by = '10'
    context_object_name = 'bills_list'

    def get_queryset(self):
        try:
            name = self.request.GET['search']
        except:
            name = ''
        if (name != ''):
            object_list = Entry.objects.all().filter(seller_id=self.request.user.username).filter(
                bill_id__icontains=name)
        else:
            object_list = Entry.objects.all().filter(seller_id=self.request.user.username)
        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(BillsList, self).dispatch(*args, **kwargs)

# Bill Detail

class BillDetailView(ListView):
    template_name = 'franchise/billdetailview.html'
    paginate_by = '10'
    context_object_name = 'item_list'

    def get_queryset(self):
        b_id = self.kwargs['id']
        bill = Bill.objects.get(bill_id=b_id)
        return Item.objects.all().filter(bill=bill)

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(BillDetailView, self).dispatch(*args, **kwargs)


# View Orders List

class SalesList(ListView):
    template_name = 'franchise/saleslist.html'
    paginate_by = '10'
    context_object_name = 'sales_list'

    def get_queryset(self):
        try:
            name = self.request.GET['search']
        except:
            name = ''
        if (name != ''):
            object_list = SalesCommission.objects.all().filter(user_id=self.request.user.username).filter(
                entry__entry_id__icontains=name)
        else:
            object_list = SalesCommission.objects.all().filter(user_id=self.request.user.username).order_by('-date')
        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(SalesList, self).dispatch(*args, **kwargs)



# Create New Bill / Own Sale

@user_passes_test(lambda u: u.username.startswith('F') or u.username.startswith('S'))
@transaction.atomic
def new_bill(request):
    user = request.user
    items_formset = inlineformset_factory(Bill, Item, form=ItemForm, extra=0)
    entry_form = EntryForm(prefix='entry')
    bill_form = BillForm(prefix='bill', initial={'cash_paid': ''})
    ic_form = ItemcodeForm(prefix='ic')
    item_forms = items_formset()
    if request.method == 'POST':
        entry_form = EntryForm(request.POST, prefix='entry')
        item_forms = items_formset(request.POST)
        bill_form = BillForm(request.POST, prefix='bill')
        ic_form = ItemcodeForm(request.POST, prefix='ic')
        if bill_form.is_valid() and item_forms.is_valid() and entry_form.is_valid():

            nbill = bill_form.save(commit=False)
            nentry = entry_form.save(commit=False)

            amount = Decimal('0.00')
            change_due = Decimal('0.00')

            for item in item_forms:
                if item.cleaned_data.get('DELETE') == False:
                    nitem = item.save(commit=False)
                    amount = amount + nitem.total

            if nbill.cash_paid < amount:
                return HttpResponseRedirect('/newbill?notif_message=Cash paid less than total bill amount.')

            customer_id = nentry.customer_id
            staff_id = nbill.staff_id
            nbill.amount = amount
            cash_paid = nbill.cash_paid
            nbill.change_due = cash_paid - amount
            nbill.save()
            staff = Staff.objects.get(user__username=staff_id)
            if user.username.startswith('S'):
                franchise = Staff.objects.get(user=user).franchise
            else:
                franchise = Franchise.objects.get(user=user)

            lvl1_amt = Decimal('0.00')
            lvl2_amt = Decimal('0.00')
            franchise_amt = Decimal('0.00')
            staff_amt = Decimal('0.00')
            charity_amt = Decimal('0.00')

            for item in item_forms:
                if item.cleaned_data.get('DELETE') == False:
                    nitem = item.save(commit=False)
                    nitem.bill = nbill
                    item_code = nitem.itemcode
                    stock_item = StockProduct.objects.get(sp_id=item_code)
                    l1share = Decimal(stock_item.l1_share)
                    l2share = Decimal(stock_item.l2_share)
                    franchiseshare = Decimal(stock_item.franchise_share)
                    staffshare = Decimal(stock_item.staff_share)
                    charityshare = Decimal(stock_item.charity_share)
                    if stock_item.lumpsum == False:
                        lvl1_amt += Decimal((amount * l1share) / 100)
                        lvl2_amt += Decimal((amount * l2share) / 100)
                        franchise_amt += Decimal((amount * franchiseshare) / 100)
                        staff_amt += Decimal((amount * staffshare) / 100)
                        charity_amt += Decimal((amount * charityshare) / 100)
                    else:
                        lvl1_amt += l1share
                        lvl2_amt += l2share
                        franchise_amt += franchiseshare
                        staff_amt += staffshare
                        charity_amt += charityshare
                    nitem.save()

            bill_id = nbill.bill_id
            refid = nentry.referral_id

            if refid == "" and customer_id == "":
                franchise.account_balance += franchise_amt
                franchise.save()
                franchise_comm = SalesCommission.objects.create(user_id=franchise.user.username, date=datetime.date.today(),
                                                                commission=franchise_amt)
                franchise_comm.save()
                request.session['entry_id'] = ""
                request.session['bill_id'] = bill_id
                return HttpResponseRedirect('/billdetail/')

            rf = 0
            if refid == "":
                refid = gen_refid(2)
                rf = 1
            else:
                try:
                    referrer = Entry.objects.get(entry_id=refid)
                    referrer.use_count += 1
                    referrer.save()
                except ObjectDoesNotExist:
                    refid = gen_refid()
                    referrer = Entry.objects.get(entry_id=refid)
                    referrer.use_count += 1
                    referrer.save()

            nentry.referral_id = refid
            nentry.seller_id = franchise.user.username
            nentry.bill_id = bill_id
            nentry.purchase_value = amount
            nentry.limit = amount + add_to_limit
            nentry.save()
            eid = nentry.entry_id


            lvl1id = refid
            trans1 = Transaction()
            trans1.from_id = eid
            trans1.to_id = lvl1id
            trans1.amount = lvl1_amt
            trans1.save()
            lvl2id = ReferralGraph.objects.get(child=refid).parent
            trans2 = Transaction()
            trans2.from_id = eid
            trans2.to_id = lvl2id
            trans2.amount = lvl2_amt

            lvl1_entry = Entry.objects.get(entry_id=lvl1id)
            lvl2_entry = Entry.objects.get(entry_id=lvl2id)
            lvl1_customer_id = lvl1_entry.customer_id
            lvl2_customer_id = lvl2_entry.customer_id
            lvl1_customer = Customer.objects.get(user__username=lvl1_customer_id)
            lvl2_customer = Customer.objects.get(user__username=lvl2_customer_id)
            lvl1_limit = lvl1_entry.limit
            lvl2_limit = lvl2_entry.limit

            lvl1_entry.balance_amount += lvl1_amt
            lvl1_customer.account_balance += lvl1_amt
            if rf ==0 :
                    smsAPI2(lvl1_customer.user.mobile_number, "Congrats! " + str(customer_id) + " has made a purchase for Rs " + str(amount) + " & Rs " + str(lvl1_amt) + " has been credited your acnt.")
            else :
                    smsAPI2(lvl1_customer.user.mobile_number, "An amount of Rs " + str(lvl1_amt) + " has been credited to your account and your current balance is Rs " + str(lvl1_customer.account_balance)")
            lvl1_entry.save()
            lvl1_customer.save()

            if lvl2_entry.close==1:
                AddSurplus(eid,lvl2_amt)
            elif lvl2_entry.balance_amount + lvl2_amt <= lvl2_limit or lvl2_entry.unlimited == True:
                lvl2_entry.balance_amount += lvl2_amt
                lvl2_customer.account_balance += lvl2_amt
                lvl2_entry.save()
                lvl2_customer.save()
                trans2.save()
                smsAPI2(lvl2_customer.user.mobile_number, "An amount of Rs " + str(lvl2_amt) + " has been credited to your account and your current balance is Rs " + str(lvl2_customer.account_balance)")
            else:
                tolvl2 = lvl2_limit - lvl2_entry.balance_amount
                surplus = lvl2_amt - tolvl2
                lvl2_entry.balance_amount += tolvl2
                lvl2_entry.close=1
                lvl2_customer.account_balance += tolvl2
                lvl2_entry.save()
                lvl2_customer.save()
                Charity.objects.create(user_id=customer_id, name=customer_name, amount=surplus)
                trans2.save()
                smsAPI2(lvl2_customer.user.mobile_number, "An amount of Rs " + str(lvl2_amt) + " has been credited to your account and your current balance is Rs " + str(lvl2_customer.account_balance)")

            franchise.account_balance += franchise_amt
            franchise.save()
            franchise_comm = SalesCommission.objects.create(user_id=franchise.user.username, date=datetime.date.today(),
                                                            entry=nentry, commission=franchise_amt)
            franchise_comm.save()

            staff.account_balance += staff_amt
            staff.save()
            staff_comm = SalesCommission.objects.create(user_id=staff.user.username, date=datetime.date.today(), entry=nentry,
                                                        commission=staff_amt)
            staff_comm.save()

            customer_name = PgUser.objects.get(username=customer_id).name
            Charity.objects.create(user_id=customer_id, name=customer_name, amount=charity_amt)

            if lvl1_entry.use_count == 2 or lvl1_entry.use_count == 4:
                parent = lvl2id
            else:
                parent = lvl1id
            rg = ReferralGraph()
            rg.parent = parent
            rg.child = eid
            rg.save()

            request.session['entry_id'] = eid
            request.session['bill_id'] = bill_id
            return HttpResponseRedirect('/billdetail/')

    return render(request, 'franchise/newbill.html',
                  {"item_forms": item_forms, "bill_form": bill_form, "entry_form": entry_form, "ic_form": ic_form,})


def AddSurplus(eid,amt):
    sur_entry = Entry.objects.filter(use_count__gte=2, unlimited=False, close=0).all()[0]
    sur_customer = Customer.objects.get(user__username=sur_entry.customer_id)
    if sur_entry.balance_amount + amt > sur_entry.limit:
        surplus = sur_entry.limit - sur_entry.balance_amount
        tocharity = amt - surplus
        sur_entry.balance_amount += surplus
        sur_entry.close=1
        sur_customer.account_balance += surplus
        sur_entry.save()
        sur_customer.save()
        Charity.objects.create(user_id=sur_entry.customer_id, name=sur_customer.user.name, amount=tocharity)
    else:
        sur_entry.balance_amount += amt
        sur_customer.account_balance += amt
        sur_entry.save()
        sur_customer.save()

    trans = Transaction()
    trans.from_id = eid
    trans.to_id = sur_entry.entry_id
    trans.amount = amt
    trans.save()


# Create New Associate Bill entry

@user_passes_test(lambda u: u.username.startswith('F') or u.username.startswith('S'))
@transaction.atomic
def assoc_bill(request):
    user = request.user
    entry_form = AssocEntryForm(prefix='assocentry', initial={'purchase_value': ''})
    if request.method == 'POST':
        entry_form = AssocEntryForm(request.POST, prefix='assocentry')
        if entry_form.is_valid():
            data = entry_form.cleaned_data
            store_name = data['store_name']
            category = data['category']
            refid = data['referral_id']
            amount = data['purchase_value']
            customer_id = data['customer_id']
            seller = Associate.objects.get(store_name=store_name)
            ap = AssociateProduct.objects.filter(store_id=seller.store_id, category__category_name=category)[0]
            nentry = Entry()
            if user.username.startswith('S'):
                franchise = Staff.objects.get(user=user).franchise
            else:
                franchise = Franchise.objects.get(user=user)
            if refid == "":
                refid = gen_refid(2)
            else:
                try:
                    referrer = Entry.objects.get(entry_id=refid)
                    referrer.use_count += 1
                    referrer.save()
                except ObjectDoesNotExist:
                    refid = gen_refid()
                    referrer = Entry.objects.get(entry_id=refid)
                    referrer.use_count += 1
                    referrer.save()

            l1share = ap.l1_share
            l2share = ap.l2_share
            franchiseshare = ap.franchise_share
            charityshare = ap.charity_share

            lvl1_amt = Decimal('0.00')
            lvl2_amt = Decimal('0.00')
            franchise_amt = Decimal('0.00')
            charity_amt = Decimal('0.00')
            associate_amt = Decimal('0.00')

            if ap.lumpsum == False:
                lvl1_amt = Decimal((amount * ap.commission * l1share) / 10000)
                lvl2_amt = Decimal((amount * ap.commission * l2share) / 10000)
                franchise_amt = Decimal((franchiseshare * ap.commission * amount) / 10000)
                charity_amt = Decimal((charityshare * ap.commission * amount) / 10000)
                associate_amt = Decimal((ap.commission * amount) / 100)
            else:
                lvl1_amt = l1share
                lvl2_amt = l2share
                franchise_amt = franchiseshare
                charity_amt = charityshare
                associate_amt = Decimal(ap.commission)

            
            seller.account_balance += associate_amt
            seller.save()
            nentry.referral_id = refid
            nentry.seller_id = seller.store_id
            nentry.customer_id = customer_id
            nentry.purchase_value = amount
            nentry.limit = amount
            nentry.is_own_sale = False
            nentry.save()

            eid = nentry.entry_id
            lvl1id = refid
            trans1 = Transaction()
            trans1.from_id = eid
            trans1.to_id = lvl1id
            trans1.amount = lvl1_amt
            trans1.save()
            lvl2id = ReferralGraph.objects.get(child=refid).parent
            trans2 = Transaction()
            trans2.from_id = eid
            trans2.to_id = lvl2id
            trans2.amount = lvl2_amt

            lvl1_entry = Entry.objects.get(entry_id=lvl1id)
            lvl2_entry = Entry.objects.get(entry_id=lvl2id)
            lvl1_customer_id = lvl1_entry.customer_id
            lvl2_customer_id = lvl2_entry.customer_id
            lvl1_customer = Customer.objects.get(user__username=lvl1_customer_id)
            lvl2_customer = Customer.objects.get(user__username=lvl2_customer_id)
            lvl1_limit = lvl1_entry.limit
            lvl2_limit = lvl2_entry.limit

            lvl1_entry.balance_amount += lvl1_amt
            lvl1_customer.account_balance += lvl1_amt
            lvl1_entry.save()
            lvl1_customer.save()
            if lvl2_entry.close==1:
                AddSurplus(eid,lvl2_amt)
            elif lvl2_entry.balance_amount + lvl2_amt <= lvl2_limit or lvl2_entry.unlimited == True:
                lvl2_entry.balance_amount += lvl2_amt
                lvl2_customer.account_balance += lvl2_amt
                lvl2_entry.save()
                lvl2_customer.save()
                trans2.save()
            else:
                tolvl2 = lvl2_limit - lvl2_entry.balance_amount
                surplus = lvl2_amt - tolvl2
                lvl2_entry.balance_amount += tolvl2
                lvl2_entry.close=1
                lvl2_customer.account_balance += tolvl2
                lvl2_entry.save()
                lvl2_customer.save()
                Charity.objects.create(user_id=customer_id, name=customer_name, amount=surplus)
                trans2.save()



            franchise.account_balance += franchise_amt
            franchise.save()
            franchise_comm = SalesCommission.objects.create(user_id=franchise.user.username, date=datetime.date.today(),
                                                            entry=nentry, commission=franchise_amt)
            franchise_comm.save()
            associate_comm = SalesCommission.objects.create(user_id=seller.store_id, date=datetime.date.today(),
                                                            entry=nentry, commission=associate_amt)
            associate_comm.save()

            customer_name = PgUser.objects.get(username=customer_id).name
            Charity.objects.create(user_id=customer_id, name=customer_name, amount=charity_amt)

            if lvl1_entry.use_count == 2 or lvl1_entry.use_count == 4:
                parent = lvl2id
            else:
                parent = lvl1id
            rg = ReferralGraph()
            rg.parent = parent
            rg.child = eid
            rg.save()

            return HttpResponseRedirect('/message?message=Associate bill entry successful.')

    return render(request, 'franchise/assocbill.html', {"entry_form": entry_form,})


# Bill - detailed view
def bill_detail(request):
    eid = request.session['entry_id']
    bill_id = request.session['bill_id']
    bill = Bill.objects.get(bill_id=bill_id)
    franchise = Franchise.objects.get(user=request.user)
    item_list = Item.objects.filter(bill=bill)

    if eid == "":
        return render(request, 'franchise/billdetail.html',
                  {"entry": None, "franchise": franchise, "bill": bill, "item_list": item_list, "customer": None})
    else:
        entry = Entry.objects.get(entry_id=eid)
        customer = Customer.objects.get(user__username=entry.customer_id)
        return render(request, 'franchise/billdetail.html',
                  {"entry": entry, "franchise": franchise, "bill": bill, "item_list": item_list, "customer": customer})


# ----------------------------------------------------------------
#                      Staff Pages
# ----------------------------------------------------------------


# View Daily sales & commission

class StaffSalesList(ListView):
    template_name = 'staff/staffsale.html'
    paginate_by = '10'
    context_object_name = 'staff_sales'

    def get_queryset(self):
        try:
            name = self.request.GET['search']
        except:
            name = ''
        if (name != ''):
            object_list = SalesCommission.objects.all().filter(user_id=self.request.user.username).filter(
                entry__entry_id__icontains=name)
        else:
            object_list = SalesCommission.objects.all().filter(user_id=self.request.user.username).order_by('-date')
        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('S')))
    def dispatch(self, *args, **kwargs):
        return super(StaffSalesList, self).dispatch(*args, **kwargs)


# ----------------------------------------------------------------
#                      Custom Functions
# ----------------------------------------------------------------

# Choose a Entry ID at 50% probability

"""def choose_refid():
    m = random.randint(0, 10)
    if m < 5:
        return gen_refid()
    else:
        return company_lvl1_entry"""


# Generate random Entry IDs

def gen_refid(i=1):
    k = 0
    i -= 1
    while k == 0:
        i += 1
        k = Entry.objects.filter(use_count=i, unlimited=False).count()
    rand_idx = random.randint(0, k - 1)
    rand_entry = Entry.objects.filter(use_count=i, unlimited=False).all()[rand_idx]
    if rand_entry.entry_id in exclude_list:
        if i < 10:
            return gen_refid(i + 1)
        else:
            return rand_entry.entry_id
    else:
        return rand_entry.entry_id


# AJAX Request

def new_item(request):
    if request.method == 'POST':
        spid = request.POST.get('spid')
        response_data = {}
        sp = StockProduct.objects.get(sp_id=spid)
        response_data['itemname'] = sp.name
        mrp = sp.price.mrp
        response_data['total'] = int(mrp)
        response_data['spid'] = spid
        response_data['qty'] = 1

        return HttpResponse(
            json.dumps(response_data),
            content_type="application/json"
        )
    else:
        return HttpResponse(
            json.dumps({"total": "0", "qty": "0", "spid": "" + spid, "itemname": "null",}),
            content_type="application/json"
        )


# AJAX Request

def new_customer(request):
    response_data = {}
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
        except:
            response_data['error'] = "Error while reading input data"
            return HttpResponse(json.dumps(response_data),content_type="application/json")

        if not name:
            response_data['error'] = "Please give valid name"
            return HttpResponse(json.dumps(response_data),content_type="application/json")

        try:
            validate_email(email)
        except:
            response_data['error'] = "Please give valid email"
            return HttpResponse(json.dumps(response_data),content_type="application/json")

        try:
            phone_obj = re.match( r'^(\+91)?\d{10}$', phone, re.M|re.I)
            if not phone_obj:
                response_data['error'] = "Please input valid phone number"
                return HttpResponse(json.dumps(response_data),content_type="application/json")
        except:
            response_data['error'] = "Please give valid phone number"
            return HttpResponse(json.dumps(response_data),content_type="application/json")
        try:
            pwd = PgUser.objects.make_random_password()
            username = username_gen()
        except:
            response_data['error'] = "Error while generatng user credentials"
            return HttpResponse(json.dumps(response_data),content_type="application/json")
        try:
            with transaction.atomic():
                user = PgUser.objects.create_user(username=username, password=pwd, email=email, name=name, mobile_number=phone)
                ncustomer = Customer.objects.create(user=user)
                response_data['customer_id'] = name
        except:
            response_data['error'] = "Oops...We couldn't create new customer. Please check input details."
            return HttpResponse(json.dumps(response_data),content_type="application/json")
        try:
            smsAPI2(phone,"Welcome to Mini-ERP. Your UID is " + str(username) + " PW is " + str(pwd) + " . Log into the website to confirm your acnt and change your password")
        except:
            response_data['error'] = "Error while sending SMS"
            return HttpResponse(json.dumps(response_data),content_type="application/json")

        return HttpResponse(json.dumps(response_data),content_type="application/json")
    else:
        response_data['error'] = "Error in request method!"
        return HttpResponse(json.dumps(response_data),content_type="application/json")


# Generate random valid Username

def username_gen():
    user = "C" + str(random.randrange(100000000000, 999999999999))
    try:
        current_user=PgUser.objects.get(username=user)
        return username_gen()
    except:
        return user



# Recharge API

def rechargeAPI(rc,customer):
    update_last_login(None, customer.user)
    last_login = customer.user.last_login
    new_rcdict = rc_dict
    new_rcdict['operator']=str(rc.operator_code)
    new_rcdict['subscriber']=rc.number
    new_rcdict['amount']=str(rc.amount)
    new_rcdict['session']=str(rc.recharge_id)
    resp = requests.post('recharge-api-url',data=new_rcdict)
    k=resp.text
    re_1 = r'Token:(?P<token>\w+)'
    re_2 = r'Status:(?P<status>\w+)'
    token=0
    status='Z'
    result1 = re.search(re_1,k)
    if result1:
        token = result1.group('token')
    result2 = re.search(re_2,k)
    if result2:
        status = result2.group('status')
    return token,status

def statusCheckAPI(token):
    API_URL = "recharge-api-url/status?token="+str(token)
    resp = requests.get(API_URL)
    print(resp.text)
    return 0

def smsAPI(recipients,content):
    numbers=""
    for customer in recipients:
        numbers+=str(customer.user.mobile_number)+","
    API_URL = "Smsapi/send?user="+ erootID +"&password="+ erootPass+"&to="+numbers+"&message="+content+"&gateway=ALERT"
    resp = requests.get(API_URL)

def smsAPI2(number,content):
    API_URL = "Smsapi/send?user="+ erootID +"&password="+ erootPass +"&to="+str(number)+"&message="+content+"&gateway=ALERT"
    resp = requests.get(API_URL)


# ----------------------------------------------------------------
#          Stock Management
# ----------------------------------------------------------------

# View Own Stock - For Franchises

class StockList(ListView):
    template_name = 'franchise/stocklist.html'
    paginate_by = '10'
    context_object_name = 'stock_list'

    def get_queryset(self):
        object_list = Stock.objects.all().filter(user_id=self.request.user.username)
        return object_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(StockList, self).dispatch(*args, **kwargs)


# Request Stock

def request_stock(request):
    tag_objs = Tag.objects.all()
    tags = []
    for obj in tag_objs:
        tags.append(obj.slug)
    json_tags = json.dumps(tags)
    return render(request, 'franchise/requeststock.html', {'tags': json_tags})


# Autocomplete - AJAX request

def autocomplete_tags(request):
    term = request.GET.get('term')  # jquery-ui.autocomplete parameter
    tags = Tag.objects.filter(slug__istartswith=term)
    res = []
    for tag in tags:
        dict = {'id': tag.id, 'label': tag.slug, 'value': tag.slug}
        res.append(dict)
    return HttpResponse(json.dumps(res))


# Stock Search - AJAX request

def stock_search(request):
    if request.method == 'POST':
        tag_list = request.POST.getlist('tag[]')
        response_data = {}
        jsonobj = {}
        allstock = Stock.objects.filter(user_id='pgadmin')
        for value in tag_list:
            stocks = allstock.filter(stock_product__tags__slug__iexact=value.strip())
        stocks = list(stocks)
        k = 0
        for stock in stocks:
            jsonobj[k] = stock.as_json()
            k += 1
        return HttpResponse(
            json.dumps(jsonobj),
            content_type="application/json"
        )
    else:
        response_data = {}
        return HttpResponse(
            json.dumps(response_data),
            content_type="application/json"
        )


# Stock Checkout

@user_passes_test(lambda u: u.username.startswith('F'))
@transaction.atomic
def stock_checkout(request):
    params = request.POST.get('json')
    yaml_data = yaml.load(params)
    srequest = StockRequest()
    srequest.franchise_id = request.user.username
    franchise = Franchise.objects.get(user=request.user)
    amount = Decimal('0.00')
    for item in yaml_data:
        amount += int(item["Quantity"]) * int(item["Product Price"])

    srequest.amount = amount
    srequest.save()

    for item in yaml_data:
        citem = CartItem()
        spid = item["Product ID"]
        qty = int(item["Quantity"])
        citem.itemcode = spid
        citem.itemname = item["Product Name"]
        citem.quantity = qty
        sp = StockProduct.objects.get(sp_id=spid)
        stck = Stock.objects.get(stock_product=sp,user_id='pgadmin')

        if qty<0 or qty>stck.quantity:
            return HttpResponseRedirect('/requeststock')

        citem.total = int(item["Quantity"]) * int(item["Product Price"])
        amount += citem.total
        citem.stock_request = srequest
        citem.save()

    item_list = CartItem.objects.filter(stock_request=srequest)

    return render(request, 'franchise/stockcheckout.html',
                  {"franchise": franchise, "srequest": srequest, "item_list": item_list,})


# View status of requests

class RequestsView(ListView):
    template_name = 'franchise/viewrequests.html'
    paginate_by = '10'
    context_object_name = 'requests_list'

    def get_queryset(self):
        requests_list = StockRequest.objects.filter(franchise_id=self.request.user.username).order_by('-sr_id')
        return requests_list

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(RequestsView, self).dispatch(*args, **kwargs)


# View details of each Stock Request

class RequestDetailView(ListView):
    template_name = 'franchise/viewrequestdetail.html'
    paginate_by = '10'
    context_object_name = 'cart_list'

    def get_queryset(self):
        sr_id = self.kwargs['id']
        srequest = StockRequest.objects.get(sr_id=sr_id)
        if srequest.franchise_id == self.request.user.username:
            return CartItem.objects.all().filter(stock_request=srequest)

    def get_context_data(self, *args, **kwargs):
        context = super(RequestDetailView, self).get_context_data(*args, **kwargs)
        context['request_id'] = self.kwargs['id']
        return context

    @method_decorator(user_passes_test(lambda u: u.username.startswith('F')))
    def dispatch(self, *args, **kwargs):
        return super(RequestDetailView, self).dispatch(*args, **kwargs)


# ----------------------------------------------------------------
#             Admin Pages
# ----------------------------------------------------------------

@user_passes_test(lambda u: u.is_superuser)
def all_requests_detail(request, id):
    srequest = StockRequest.objects.get(sr_id=id)
    cart_list = CartItem.objects.filter(stock_request=srequest)
    tot = cart_list.aggregate(Sum('quantity')).get('quantity__sum', 0.00)
    return render(request, 'admin/allrequestsdetail.html', {"cart_list": cart_list, "srequest": srequest, "totalquantity": tot})

@user_passes_test(lambda u: u.is_superuser)
def ajax_accept_order(request):
    srid = request.POST.get('sr_id')
    srequest = StockRequest.objects.get(sr_id=srid)
    srequest.status = "Success"
    srequest.save()
    item_list = CartItem.objects.filter(stock_request=srequest)
    for item in item_list:
        new_sp = StockProduct.objects.get(sp_id=item.itemcode)
        new_sk, created = Stock.objects.get_or_create(user_id=srequest.franchise_id,stock_product=new_sp)
        new_sk.quantity+=item.quantity
        new_sk.save()
        print(new_sk)
    response_data = {}
    response_data['status'] = "Success"
    return HttpResponse(
        json.dumps(response_data),
        content_type="application/json"
    )

@user_passes_test(lambda u: u.is_superuser)
def ajax_cancel_order(request):
    srid = request.POST.get('sr_id')
    srequest = StockRequest.objects.get(sr_id=srid)
    srequest.status = "Cancelled"
    srequest.save()
    response_data = {}
    response_data['status'] = "Cancelled"

    return HttpResponse(
        json.dumps(response_data),
        content_type="application/json"
    )

@user_passes_test(lambda u: u.is_superuser)
@transaction.atomic
def admin_recharge(request):
    if request.method == 'POST':
        form = AdminRechargeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            cust_id = data['customer_id']
            customer = Customer.objects.get(user__username=cust_id)
            curr_balance = customer.account_balance
            amt = int(data['amount'])
            if amt + rchg_service_charge > curr_balance :
                return HttpResponseRedirect('/message?message=Your account balance is insufficient.')
            new_amt = customer.account_balance - amt - rchg_service_charge
            customer.account_balance = new_amt
            customer.save()
            rc = Recharge()
            number = data['number'].replace(",","")
            code = Operator.objects.get(name=data['operator']).code
            rc.operator_code = code
            rc.amount = amt
            rc.number = number
            rc.customer_id = request.user.username
            rc.success = True
            rc.save()
            return HttpResponseRedirect('/message?message=Your request has been saved.')
    else:
        form = AdminRechargeForm()
    return render(request, 'admin/recharge.html', {'form': form})

@user_passes_test(lambda u: u.is_superuser)
def sendemail(request):
    if request.method == 'POST':

        recipients = request.POST.getlist('recipients')
        if not recipients:
            return HttpResponseRedirect('/sendemail?notif_message=Select at least one recipient.')

        subject = request.POST['email_subject']
        content = request.POST['email_content']

        email = EmailMessage(subject, content, usermailID, bcc=recipients)
        email.send(fail_silently=False)
        return HttpResponseRedirect('/message?message=Your email has been sent.')
    else:
        customers = Customer.objects.exclude(user__email__isnull=True).exclude(user__email__exact='')
        franchises = Franchise.objects.exclude(user__email__isnull=True).exclude(user__email__exact='')

        return render(request, 'admin/sendemail.html', {'customers': customers, 'franchises': franchises})

@user_passes_test(lambda u: u.is_superuser)
def sendsms(request):
    if request.method == 'POST':

        recipient_usernames = request.POST.getlist('recipients')

        if not recipient_usernames:
            return HttpResponseRedirect('/sendsms?notif_message=Select at least one recipient.')

        content = request.POST['sms_content']
        recipients = []
        for recipient_username in recipient_usernames:
            try:
                customer = Customer.objects.get(user__username=recipient_username)
                recipients.append(customer)
            except:
                pass
        if not recipients:
            return HttpResponseRedirect('/sendsms?notif_message=Recipient details could not be fetched.')

        #API Call
        smsAPI(recipients,content)
        return HttpResponseRedirect('/message?message=Your message has been sent.')
    else:
        customers = Customer.objects.all()
        return render(request, 'admin/sendsms.html', {'customers': customers})


# ----------------------------------------------------------------
#               New Pages
# ----------------------------------------------------------------

class CharityList(ListView):
    template_name = 'common/charity.html'
    paginate_by = '8'
    context_object_name = 'charity_list'

    def get_queryset(self):
        object_list = Charity.objects.all().order_by('-datetime')
        return object_list

    def dispatch(self, *args, **kwargs):
        return super(CharityList, self).dispatch(*args, **kwargs)

class AllRequestsList(ListView):
    template_name = 'admin/allrequests.html'
    paginate_by = '5'
    context_object_name = 'requests_list'

    def get_queryset(self):
        object_list = StockRequest.objects.all()
        return object_list

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def dispatch(self, *args, **kwargs):
        return super(AllRequestsList, self).dispatch(*args, **kwargs)

@user_passes_test(lambda u: u.is_superuser)
def make_payment(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            data =form.cleaned_data
            user_id = data['user_id']
            amount = int(data['amount'])
            remarks = data['remarks']
            user_cat = user_id[:1]
            if user_cat == 'C':
                try:
                    receiver = Customer.objects.get(user__username= user_id)
                except:
                    return HttpResponseRedirect("/makepayment?notif_message=Customer with given ID doesn't exist.")
            elif user_cat == 'F':
                try:
                    receiver = Franchise.objects.get(user__username= user_id)
                except:
                    return HttpResponseRedirect("/makepayment?notif_message=Franchise with given ID doesn't exist.")
            elif user_cat == 'S':
                try:
                    receiver = Staff.objects.get(user__username= user_id)
                except:
                    return HttpResponseRedirect("/makepayment?notif_message=Staff with given ID doesn't exist.")
            if receiver.account_balance >= amount:
                receiver.account_balance = receiver.account_balance - amount
                receiver.save()
            else:
                return HttpResponseRedirect("/makepayment?notif_message=Account balance is less than amount to be paid.")
            form.save()
            return HttpResponseRedirect('/message?message=The payment was successfully processed.')
    form = PaymentForm()
    return render(request, 'admin/makepayment.html',  {'form': form})

# Terms n conditions accept check

def tncaccept(user):
    user_obj = Customer.objects.get(user=user)
    tnc = user_obj.tnc
    return tnc

#tnc view
@login_required
def tncview(request):
    if request.method == 'POST':
        value = request.POST.get("checked", None)
        if value == "on":
            user = Customer.objects.get(user = request.user)
            user.tnc = True
            user.save()
            smsAPI2(user.user.mobile_number,"Congrats Your acnt is now confirmed you may now start referring and make use of the never before opportunity. Wish you all the best. PG")
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect('/termsandconditions')
    else:
        return render(request, 'termsandconditions.html')

def smsreceiver(request):
    number = str(request.GET.get('number'))[-10:]
    message = str(request.GET.get('message'))
    message_log = ReceivedMessage()
    message_log.mobile_number = number
    message_log.message = message
    message_log.save()
    customer = Customer.objects.get(user__mobile_number=int(number))
    lastlog = customer.user.last_login.replace(tzinfo=None)
    time_now = datetime.datetime.now().replace(tzinfo=None)
    time_diff = time_now - lastlog
    if time_diff.days > 15:
        #sendsms()
        smsAPI2(str(customer.user.mobile_number),"Your account is not active as you haven't logged in 15 days.")
    else:
        curr_balance = customer.account_balance
        rc_list=message.split()
        rc_num=int(rc_list[0])
        rc_op=rc_list[1]
        rc_amt=int(rc_list[2])
        rc = Recharge()
        code = Operator.objects.get(name=rc_op).code
        rc.operator_code = code
        rc.amount = rc_amt
        rc.number = rc_num
        rc.customer_id = customer.user.username
        rc.save()
        customer.account_balance -= rc_amt
        customer.save()
        token,status=rechargeAPI(rc,customer)
        if status=='F':
            customer.account_balance += rc_amt
            customer.save()
            smsAPI2(str(customer.user.mobile_number),"Sorry v r unable to execute ur order at present. Ur acct balance is Rs " + str(customer.account_balance) + ".Pls try again later.Have a great day. PG ")
        else:
            rc.success = True
            rc.save()
            smsAPI2(str(customer.user.mobile_number),"Thank you for your valuable order and the same shall be executed soon. Your acct balance will be Rs " + str(customer.account_balance))

#def addmoney(customer_id,amount):



def rechargeAPI(rc,customer):
    update_last_login(None, customer.user)
    last_login = customer.user.last_login
    new_rcdict = rc_dict
    new_rcdict['operator']=str(rc.operator_code)
    new_rcdict['subscriber']=rc.number
    new_rcdict['amount']=str(rc.amount)
    new_rcdict['session']=str(rc.recharge_id)
    resp = requests.post('recharge-api-url',data=new_rcdict)
    k=resp.text
    print(k)
    re_1 = r'Token:(?P<token>\w+)'
    re_2 = r'Status:(?P<status>\w+)'
    token=0
    status='Z'
    result1 = re.search(re_1,k)
    if result1:
        token = result1.group('token')
    result2 = re.search(re_2,k)
    if result2:
        status = result2.group('status')
    return token,status

# Forgot password page
def forgot_password(request):
    if request.method == 'POST':
        if request.POST['submit'] == "gen_code":
            try:
                mobile_number = request.POST['mobile_number']
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Please provide a mobile number.")
            try:
                user = Customer.objects.get(user__mobile_number = mobile_number)
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Please provide a valid mobile number.")
            try:
                # Generate reset code
                reset_code = random.randrange(10000, 100000)
                # Update existing reset code or create new record
                try:
                    user_otp_entry, created = ForgotPassword.objects.update_or_create(
                        user = user,
                        defaults = {'reset_code': reset_code}
                        )
                except:
                    return HttpResponseRedirect("/forgotpassword?notif_message=Error generating otp. Please contact our support team.")
                # Send reset code as SMS
                smsAPI2(user.user__mobile_number, "Your code to reset password is " + str(reset_code))
                return HttpResponseRedirect("/forgotpassword?notif_message=Reset code has been sent to your mobile number successfully. "
                    + "Please provide the same in below form to reset your password.")
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Oops! We couldn't generate reset code. Please contact our support team.")

        elif request.POST['submit'] == "check_reset_code":
            try:
                mobile_number = request.POST['mobile_number']
                reset_code = int(request.POST['reset_code'])
                new_password = request.POST['new_password']
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Please provide mobile number and valid reset code.")
            try:
                user = Customer.objects.get(user__mobile_number = mobile_number)
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Please provide a valid mobile number.")
            try:
                # Get reset code entry
                user_otp_entry = ForgotPassword.objects.get(user = user)
            except:
                return HttpResponseRedirect("/forgotpassword?notif_message=Please generate reset code first.")

            if user_otp_entry.reset_code == reset_code:
                try:
                    from zxcvbn import zxcvbn
                    results = zxcvbn(new_password)
                    if results['score'] < settings.PASSWORD_MINIMUM_SCORE:
                        return HttpResponseRedirect("/forgotpassword?notif_message=Password is too common!")
                    else:
                        user_obj = user.user
                        user_obj.set_password(new_password)
                        user_obj.save()
                        user_otp_entry.delete()
                        return HttpResponseRedirect("/forgotpassword?notif_message=Success!")
                except:
                    return HttpResponseRedirect("/forgotpassword?notif_message=Error updating your password. Please try again or contact our support team.")
            else:
                return HttpResponseRedirect("/forgotpassword?notif_message=The reset code you entered doesn't match with generated one. Plese try again.")
            return HttpResponseRedirect("/forgotpassword?notif_message=Oops! An error occured. Please try again.")
        else:
            return HttpResponseRedirect("/forgotpassword?notif_message=Error in form submitted. Please try again.")
    else:
        return render(request, 'common/forgot_password.html')

# Terms and conditions full page view
def tnc_full_view(request):
    return render(request, 'termsandconditions_fullpage.html')

# Privacy Policy view
def privacy_policy(request):
    return render(request, 'privacy_policy.html')
