from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from portal.models import *
from django.utils.translation import ugettext_lazy as _

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from django.contrib.admin import SimpleListFilter, DateFieldListFilter
from django.contrib.admin.views.main import ChangeList

class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = PgUser
        fields = ('name', 'mobile_number', 'username', 'email')

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """
    password = ReadOnlyPasswordHashField(
                label=_("Password"),
		help_text=_(
		    "Raw passwords are not stored, so there is no way to see this "
		    "user's password, but you can change the password using "
		    "<a href=\"../password/\">this form</a>."
		),
            )

    class Meta:
        model = PgUser
        fields = ('name', 'mobile_number', 'username', 'email', 'password')

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial["password"]


class UserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    form = UserChangeForm
    add_form = UserCreationForm

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = ('email',)
    list_filter = ()
    fieldsets = (
        (None, {'fields': ('name', 'mobile_number', 'username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_superuser',)}),
    )
    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'mobile_number', 'username', 'email',  'password1', 'password2')}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ()

# Now register the new UserAdmin...
admin.site.register(PgUser, UserAdmin)

#from django.contrib.auth.models import User

class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user']
    search_fields = ('user__mobile_number','user__username','user__name')
admin.site.register(Customer, CustomerAdmin)

class FranchiseAdmin(admin.ModelAdmin):
    list_display = ('user','store_name')
    search_fields = ('user__mobile_number','user__username','user__name','store_name')
admin.site.register(Franchise,FranchiseAdmin)

class AssociateAdmin(admin.ModelAdmin):
    list_display = ('contact_person','store_name','store_number')
    search_fields = ('contact_person','store_name','store_number')
admin.site.register(Associate,AssociateAdmin)

class StaffAdmin(admin.ModelAdmin):
    list_display = ('user','franchise',)
    search_fields = ('user__mobile_number','user__username','user__name','franchise__store_name','franchise__user__name')
    list_filter = ('franchise__store_name',)
admin.site.register(Staff,StaffAdmin)


class RGAdmin(admin.ModelAdmin):
    list_display = ('parent','child')
    search_fields = ('parent','child')
#admin.site.register(ReferralGraph, RGAdmin)

class StockProductAdmin(admin.ModelAdmin):
    list_display = ('sp_id','name','price','category','tag_list')
    search_fields = ('sp_id','name','price__mrp','category',)
    list_filter = ('category','tags',)

    def get_queryset(self, request):
        return super(StockProductAdmin, self).get_queryset(request).prefetch_related('tags')

    def tag_list(self, obj):
        return u", ".join(o.name for o in obj.tags.all())

admin.site.register(StockProduct, StockProductAdmin)

class ProductPriceAdmin(admin.ModelAdmin):
    exclude = ('price_id',)
#admin.site.register(ProductPrice,ProductPriceAdmin)

class PaymentAdmin(admin.ModelAdmin):
    exclude = ('payment_id',)
    search_fields = ('user_id','remarks',)
    list_filter = ('user_id',)
admin.site.register(Payment, PaymentAdmin)

class StockAdmin(admin.ModelAdmin):
    list_display = ('stock_id','stock_product','get_name','user_id','quantity',)
    search_fields = ('stock_id','stock_product','stock_product__name','user_id','quantity',)
    list_filter = ('user_id','stock_product__name',)

    def get_name(self, obj):
        return obj.stock_product.name
    get_name.short_description = 'Product Name'
    get_name.admin_order_field = 'stock_product__name'
#admin.site.register(Stock, StockAdmin)

class AssociateProductAdmin(admin.ModelAdmin):
    list_display = ('ap_id','store_id','commission','get_category',)
    search_fields = ('ap_id','store_id','commission','category__category_name',)
    list_filter = ('store_id','category__category_name',)

    def get_category(self, obj):
        return obj.category.category_name
    get_category.short_description = 'Category'
    get_category.admin_order_field = 'category__category_name'
admin.site.register(AssociateProduct, AssociateProductAdmin)

class RechargeAdmin(admin.ModelAdmin):
    list_display = ('recharge_id','customer_id','number','amount','success')
    search_fields = ('recharge_id','customer_id','number')
#admin.site.register(Recharge, RechargeAdmin)

class MyChangeList(ChangeList):
    def get_query_set(self, request):
        try:
            date_search = datetime.datetime.strptime(self.query, '%d %b %Y').date().strftime('%Y-%m-%d')
        except ValueError:
            date_search = self.query
        with temporary_value(self, 'query', date_search):
            qs = super(MyChangeList, self).get_query_set(request)
            return qs

class MonthFilter(SimpleListFilter):
    title = 'datetime'
    parameter_name = 'datetime'

    def lookups(self, request,model_admin):
        final_tuple=[]
        for i in range(1,13):
            final_tuple.append((i, datetime.date(2008, i, 1).strftime('%B')))
        return final_tuple


    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(datetime__month=self.value())
        else:
            return queryset

class CharityAdmin(admin.ModelAdmin):
    list_display = ('user_id','name','amount','datetime')
    search_fields = ('user_id','name','amount','datetime')
    list_filter = ('user_id',MonthFilter,)
admin.site.register(Charity,CharityAdmin)

class EntryAdmin(admin.ModelAdmin):
    list_display = ('entry_id','customer_id','purchase_value','referral_id','seller_id','balance_amount','get_datetime',)
    search_fields = ('entry_id','customer_id','purchase_value','referral_id','seller_id',)
    list_filter = ('is_own_sale','unlimited','seller_id')

    def get_datetime(self, obj):
        datetime=Bill.objects.get(bill_id=obj.bill_id).datetime
        return datetime
    get_datetime.short_description = 'Date & Time'
admin.site.register(Entry, EntryAdmin)

class AssociateCategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name',)
    search_fields = ('category__category_name',)
#admin.site.register(AssociateCategory, AssociateCategoryAdmin)

class SalesCommissionAdmin(admin.ModelAdmin):
    list_display = ('user_id','date','entry','commission')
    search_fields = ('user_id','date','entry__entry_id')
    list_filter = ('date',)
admin.site.register(SalesCommission, SalesCommissionAdmin)

class BillAdmin(admin.ModelAdmin):
    list_display = ('bill_id','amount','staff_id','datetime')
    search_fields = ('bill_id','staff_id','datetime')
#admin.site.register(Bill, BillAdmin)

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('trans_id','from_id','to_id','amount','datetime')
    search_fields = ('trans_id','from_id','to_id','amount','datetime')
#admin.site.register(Transaction, TransactionAdmin)

class OperatorAdmin(admin.ModelAdmin):
    list_display = ('code','name')
    search_fields = ('code','name')
#admin.site.register(Operator, OperatorAdmin)

class StockRequestAdmin(admin.ModelAdmin):
    list_display = ('sr_id','datetime','franchise_id','amount','status')
    search_fields = ('sr_id','datetime','franchise_id','status')
#admin.site.register(StockRequest, StockRequestAdmin)

class ReceivedMessageAdmin(admin.ModelAdmin):
    list_display = ('mobile_number','message')
    search_fields = ('mobile_number','message')
#admin.site.register(ReceivedMessage,ReceivedMessageAdmin)

class ForgotPasswordAdmin(admin.ModelAdmin):
    list_display = ('user','reset_code')
    search_fields = ('user','reset_code')
#admin.site.register(ForgotPassword, ForgotPasswordAdmin)
