from rest_framework import serializers
from .models import CustomUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'password')
        extra_kwargs = {
            'password': {'write_only': True}, # Password should not be readable
        }

    def create(self, validated_data):
        # Handle password hashing during user creation
        user = CustomUser.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        # Handle password hashing during user update if password is provided
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
