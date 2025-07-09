from django.contrib import admin
from .models import Guest, Reservation

@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'user_account')
    search_fields = ('first_name', 'last_name', 'email')
    autocomplete_fields = ('user_account',) # If you link guests to user accounts

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id','guest', 'room', 'check_in_date', 'check_out_date', 'status', 'total_price')
    list_filter = ('status', 'check_in_date', 'check_out_date', 'room__room_type')
    search_fields = ('guest__first_name', 'guest__last_name', 'guest__email', 'room__room_number')
    autocomplete_fields = ('guest', 'room')
    date_hierarchy = 'check_in_date'
    readonly_fields = ('total_price', 'created_at', 'updated_at') # total_price might be auto-calculated

    fieldsets = (
        (None, {
            'fields': ('guest', 'room', 'status')
        }),
        ('Booking Details', {
            'fields': ('check_in_date', 'check_out_date', 'number_of_adults', 'number_of_children', 'notes')
        }),
        ('Pricing & Timestamps', {
            'fields': ('total_price', 'created_at', 'updated_at'),
            'classes': ('collapse',) # Make this section collapsible
        }),
    )
