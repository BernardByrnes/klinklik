from rest_framework import serializers
from accounts.models import User
from tenancy.serializers import FacilitySerializer, OrganisationSerializer


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    organisation_id = serializers.UUIDField(required=False)


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserRoleGrantSerializer(serializers.Serializer):
    name = serializers.CharField()
    template_code = serializers.CharField()
    facility = serializers.CharField(allow_null=True)
    department = serializers.CharField(allow_null=True)
    department_code = serializers.CharField(allow_null=True)


class SessionResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    access_expires_at = serializers.DateTimeField()
    user = UserSummarySerializer()
    organisation = OrganisationSerializer()
    facilities = FacilitySerializer(many=True)
    roles = UserRoleGrantSerializer(many=True)
    capabilities = serializers.ListField(child=serializers.CharField())
