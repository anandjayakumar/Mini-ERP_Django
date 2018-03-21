from django.db import models

from django.core.validators import RegexValidator, MaxValueValidator

from django.contrib.auth.models import AbstractBaseUser, AbstractUser, UserManager
from django.contrib.auth.models import PermissionsMixin
from django.utils.translation import ugettext_lazy as _

import datetime
from decimal import Decimal
from taggit.managers import TaggableManager
import math, json

class PgUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=30, unique=True)
    email = models.EmailField(unique=True)
    mobile_regex = RegexValidator(regex=r'^\+?1?\d{10}$', message="Mobile Number must be 10 digits long")
    mobile_number = models.CharField(validators=[mobile_regex], max_length=10, unique=True)
    name = models.CharField(max_length=50, default='', blank=True)
    address = models.CharField(max_length=100, default='', blank=True)
    district = models.CharField(max_length=30, default='', blank=True)
    state = models.CharField(max_length=30, default='', blank=True)
    country = models.CharField(max_length=30, default='', blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=True,
        help_text=_('Designates whether the user can log into this site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    USERNAME_FIELD = 'mobile_number'
    REQUIRED_FIELDS = ['username', 'email', 'name']
    objects = UserManager()

    def __str__(self):
        return self.mobile_number

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

class Customer(models.Model):
    user = models.OneToOneField(PgUser)
    permanent_address = models.CharField(max_length=100, default='', blank=True)
    billing_address = models.CharField(max_length=100, default='', blank=True)
    account_balance = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    tnc = models.BooleanField(default = False)

    def __str__(self):
        return self.user.username

class Franchise(models.Model):
    user = models.OneToOneField(PgUser)
    store_name = models.CharField(max_length=30, default='')
    landline_number = models.BigIntegerField(default='', blank=True, null=True)
    account_balance = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def __str__(self):
        return self.user.username

class Staff(models.Model):
    user = models.OneToOneField(PgUser)
    franchise = models.ForeignKey(Franchise, null=True)
    account_balance = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def __str__(self):
        return self.user.username

class Associate(models.Model):
    store_id = models.CharField(max_length=16,primary_key=True)
    store_name = models.CharField(max_length=30, default='')
    store_number = models.CharField(max_length=30,default='', blank=True, null=True)
    contact_person = models.CharField(max_length=30, default='')
    mobile_regex = RegexValidator(regex=r'^\+?1?\d{10}$', message="Mobile Number must be 10 digits long")
    contact_number = models.CharField(validators=[mobile_regex], max_length=10, unique=True)
    secondary_contact_person = models.CharField(max_length=30, default='')
    secondary_contact_number = models.CharField(validators=[mobile_regex], max_length=10, default="0000000000")
    address = models.CharField(max_length=100, default='', blank=True)
    district = models.CharField(max_length=30, default='', blank=True)
    state = models.CharField(max_length=30, default='', blank=True)
    country = models.CharField(max_length=30, default='', blank=True)
    account_balance = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def __str__(self):
        return self.store_id

class ProductPrice(models.Model):
    id = models.AutoField(primary_key = True)
    price_id = models.CharField(max_length=16, default='')
    cost_price = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    cst = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    extra_cost = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    profit = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    vat = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    mrp = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def save(self,force_insert=False, force_update=False):
        super(ProductPrice,self).save()
        idx = self.id
        self.price_id = 'PP'+ str(idx).zfill(12)
        cost = Decimal(self.cost_price + (self.cost_price*self.cst)/100 + self.extra_cost)
        sell_price = Decimal(cost + (self.profit*self.cost_price)/100)
        x = Decimal( sell_price + (self.vat*sell_price)/100)
        self.mrp = Decimal(int(math.ceil(x / Decimal(10.0))) * 10)
        super(ProductPrice, self).save(force_insert, force_update)

    def __str__(self):
        return str(self.mrp)

class StockProduct(models.Model):
    id = models.AutoField(primary_key = True)
    sp_id = models.CharField(max_length=16, default='X')
    name = models.CharField(max_length=30, default='')
    price = models.ForeignKey(ProductPrice,null=True)
    category = models.CharField(max_length=30, default='')
    lumpsum = models.BooleanField(default=False)
    l1_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    l2_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    franchise_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    staff_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    charity_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    tags = TaggableManager()

    def save(self,force_insert=False, force_update=False):
        super(StockProduct,self).save()
        idx = self.id
        self.sp_id = 'SP'+ str(idx).zfill(12)
        super(StockProduct, self).save(force_insert, force_update)

    def __str__(self):
        return self.sp_id

    def as_json(self):
        return dict(
            sp_id = self.sp_id,
            name = self.name,
            price = int(self.price.mrp),
            tags = json.dumps(list(self.tags.slugs())))

# Associate categories
class AssociateCategory(models.Model):
    category_name = models.CharField(primary_key=True, max_length=20)

    def __str__(self):
        return self.category_name

# Associate = OutSource = Vendor

class AssociateProduct(models.Model):
    id = models.AutoField(primary_key = True)
    ap_id = models.CharField(max_length=16, default='')
    store_id = models.CharField(max_length=16, default='')
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    category = models.ForeignKey(AssociateCategory)
    lumpsum = models.BooleanField(default=False)
    l1_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    l2_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    franchise_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    charity_share = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def save(self,force_insert=False, force_update=False):
        super(AssociateProduct,self).save()
        idx = self.id
        self.ap_id = 'AP'+ str(idx).zfill(12)
        super(AssociateProduct, self).save(force_insert, force_update)

    def __str__(self):
        return self.ap_id


# We can add more fields if required

class Charity(models.Model):
    datetime = models.DateTimeField(default=datetime.datetime.now);
    user_id = models.CharField(max_length=16, blank=True, null=True)
    name = models.CharField(max_length=50, default='', blank=True)
    amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

# idk if any field is unnecessary. Need to optimize this model

class Entry(models.Model):
    id = models.AutoField(primary_key = True)
    entry_id = models.CharField(max_length=16, default='')
    referral_id = models.CharField(max_length=16, blank=True) # Entry id
    customer_id = models.CharField(max_length=16, blank=True, null=True)
    seller_id =  models.CharField(max_length=16,default='') # can be Franchise or Associate ID
    bill_id = models.CharField(max_length=16, blank=True, null=True) # No bill_id for Associate sales
    purchase_value = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    balance_amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    limit = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00')) # PV or PV+5000
    unlimited = models.NullBooleanField(default=False, blank=True, null=True)
    is_own_sale = models.BooleanField(default=True)
    use_count = models.IntegerField(default=0)
    close = models.IntegerField(default=0)

    def save(self,force_insert=False, force_update=False):
        super(Entry,self).save()
        idx = self.id
        self.entry_id = 'E'+ str(idx).zfill(12)
        super(Entry, self).save(force_insert, force_update)

    def __str__(self):
        return self.entry_id

# Bill id is used to retrieve itemlist. It has 1 - 1 relation with Entry id.
# Need to optimize this model

class Bill(models.Model):
    id = models.AutoField(primary_key = True)
    bill_id = models.CharField(max_length=16, default='')
    datetime = models.DateTimeField(default=datetime.datetime.now);
    staff_id = models.CharField(max_length=16)
    amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    cash_paid = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    change_due = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def save(self,force_insert=False, force_update=False):
        super(Bill,self).save()
        idx = self.id
        self.bill_id = 'B'+ str(idx).zfill(12)
        self.datetime = datetime.datetime.now()+datetime.timedelta(minutes=330)
        super(Bill, self).save(force_insert, force_update)

    def __str__(self):
        return self.bill_id

# It stores transactions for each entry. When money is added to first level
# and second level, it is stored in this model. So #trans = 2 X #entries
# Larger table than Entry so needs to be optimized

class Transaction(models.Model):
    id = models.AutoField(primary_key = True)
    trans_id = models.CharField(max_length=16, default='')
    from_id = models.CharField(max_length=16)  # Entry id
    to_id = models.CharField(max_length=16)    # Entry id
    amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    datetime = models.DateTimeField(default=datetime.datetime.now);

    def save(self,force_insert=False, force_update=False):
        super(Transaction,self).save()
        idx = self.id
        self.trans_id = 'TN'+ str(idx).zfill(12)
        super(Transaction, self).save(force_insert, force_update)

    def __str__(self):
        return self.trans_id

# Required to find first & second levels without accessing the Entry table
# parent = referrer, child = buyer

class ReferralGraph(models.Model):
    parent = models.CharField(max_length=16) # Entry id
    child = models.CharField(max_length=16) # Entry id

# Stores the list of items in a bill. Largest table. About 5-10 times the size
# of Entry table. Needs to be optimized.

class Item(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, null=True, blank = True)
    itemcode = models.CharField(max_length=16)
    itemname = models.CharField(max_length=30)
    quantity = models.IntegerField(default=1, blank=True)
    total = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))


class Recharge(models.Model):
    id = models.AutoField(primary_key = True)
    recharge_id = models.CharField(max_length=16, default='')
    customer_id = models.CharField(max_length=16)
    operator_code = models.CharField(max_length=16)
    amount = models.IntegerField(default=0)
    number = models.CharField(max_length=20)
    success = models.BooleanField(default=False)

    def save(self,force_insert=False, force_update=False):
        super(Recharge,self).save()
        idx = self.id
        self.recharge_id = 'R'+ str(idx).zfill(12)
        super(Recharge, self).save(force_insert, force_update)

    def __str__(self):
        return self.recharge_id

class Payment(models.Model):
    id = models.AutoField(primary_key = True)
    payment_id = models.CharField(max_length=16, default='')
    user_id = models.CharField(max_length=16, default='')
    amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    remarks = models.CharField(max_length=50, default='')
    datetime = models.DateTimeField(default=datetime.datetime.now);

    def save(self,force_insert=False, force_update=False):
        super(Payment,self).save()
        idx = self.id
        self.payment_id = 'PAY'+ str(idx).zfill(12)
        super(Payment, self).save(force_insert, force_update)

    def __str__(self):
        return self.payment_id

class Operator(models.Model):
    code = models.CharField(primary_key=True, max_length=20)
    name = models.CharField(max_length=30, default='')

    def __str__(self):
        return self.name

class SalesCommission(models.Model):
    user_id = models.CharField(max_length=16)
    date = models.DateField();
    entry = models.ForeignKey(Entry, null=True)
    commission = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

    def __str__(self):
        return self.user_id
class Stock(models.Model):
    id = models.AutoField(primary_key = True)
    stock_id = models.CharField(max_length=16, default='X')
    stock_product = models.ForeignKey(StockProduct, null=True)
    user_id = models.CharField(max_length=16, default='')
    quantity = models.IntegerField(default=0)

    def save(self,force_insert=False, force_update=False):
        super(Stock,self).save()
        idx = self.id
        self.stock_id = 'STK'+ str(idx).zfill(12)
        super(Stock, self).save(force_insert, force_update)

    def __str__(self):
        return self.stock_id

    def as_json(self):
        return dict(
            stock_id = self.stock_id,
            stock_product = self.stock_product.as_json(),
            user_id = self.user_id,
            quantity = self.quantity)

class StockRequest(models.Model):
    id = models.AutoField(primary_key = True)
    sr_id = models.CharField(max_length=16, default='')
    datetime = models.DateTimeField(default=datetime.datetime.now);
    franchise_id = models.CharField(max_length=16, default='')
    amount = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))
    STATUS_CHOICES = (
        ('Success', 'Success'),
        ('Cancelled', 'Cancelled'),
        ('Pending', 'Pending'),
    )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_CHOICES[2][1])

    def save(self,force_insert=False, force_update=False):
        super(StockRequest,self).save()
        idx = self.id
        self.sr_id = 'SR'+ str(idx).zfill(12)
        super(StockRequest, self).save(force_insert, force_update)

    def __str__(self):
        return self.sr_id

class CartItem(models.Model):
    stock_request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, null=True, blank = True)
    itemcode = models.CharField(max_length=16)
    itemname = models.CharField(max_length=30)
    quantity = models.IntegerField(default=1, blank=True)
    total = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0.00'))

class ReceivedMessage(models.Model):
    mobile_number = models.CharField(max_length=13)
    message = models.CharField(max_length=30)

#class AssociateProductCategory(models.Model):
#    category = models.CharField(max_length=30, primary_key=True)

class ForgotPassword(models.Model):
    user = models.ForeignKey(Customer)
    reset_code = models.PositiveIntegerField(validators=[MaxValueValidator(99999)])
