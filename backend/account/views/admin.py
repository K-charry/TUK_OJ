import os
import re
import xlsxwriter

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from submission.models import Submission
from utils.api import APIView, validate_serializer
from utils.decorators import super_admin_required
from utils.shortcuts import rand_str

from ..models import AdminType, ProblemPermission, User, UserProfile
from ..serializers import EditUserSerializer, UserAdminSerializer, GenerateUserSerializer
from ..serializers import ImportUserSeralizer


class UserAdminAPI(APIView):
    @swagger_auto_schema(
        request_body=(ImportUserSeralizer),
        operation_description="Import User"
    )
    @validate_serializer(ImportUserSeralizer)
    @super_admin_required
    def post(self, request):
        """
        Import User
        """
        data = request.data["users"]

        user_list = []
        for user_data in data:
            if len(user_data) != 3 or len(user_data[0]) > 32:
                return self.error(f"Error occurred while processing data '{user_data}'")
            user_list.append(User(username=user_data[0], password=make_password(user_data[1]), email=user_data[2]))

        try:
            with transaction.atomic():
                ret = User.objects.bulk_create(user_list)
                UserProfile.objects.bulk_create([UserProfile(user=user) for user in ret])
        except IntegrityError as e:
            # Extract detail from exception message
            #    duplicate key value violates unique constraint "user_username_key"
            #    DETAIL:  Key (username)=(root11) already exists.
            return self.error(str(e).split("\n")[1])

        return self.success()

    @swagger_auto_schema(
        request_body=(EditUserSerializer),
        operation_description="Edit user api"
    )
    @validate_serializer(EditUserSerializer)
    @super_admin_required
    def put(self, request):
        """
        Edit user api
        """
        data = request.data
        try:
            user = User.objects.get(id=data["id"])
        except User.DoesNotExist:
            return self.error("User does not exist")
        if User.objects.filter(username=data["username"].lower()).exclude(id=user.id).exists():
            return self.error("Username already exists")
        if User.objects.filter(email=data["email"].lower()).exclude(id=user.id).exists():
            return self.error("Email already exists")

        pre_username = user.username
        user.username = data["username"].lower()
        user.email = data["email"].lower()
        user.major = data["major"]
        user.admin_type = data["admin_type"]
        user.is_disabled = data["is_disabled"]

        if data["admin_type"] == AdminType.ADMIN:
            user.problem_permission = data["problem_permission"]
        elif data["admin_type"] == AdminType.SUPER_ADMIN:
            user.problem_permission = ProblemPermission.ALL
        else:
            user.problem_permission = ProblemPermission.NONE

        if data["password"]:
            user.set_password(data["password"])

        user.save()
        if pre_username != user.username:
            Submission.objects.filter(username=pre_username).update(username=user.username)

        UserProfile.objects.filter(user=user).update(real_name=data["real_name"])
        return self.success(UserAdminSerializer(user).data)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="id", in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="unique user id",
            ),
            openapi.Parameter(
                name="keyword", in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="user keyword",
            ),
        ],
        operation_description="Get User"
    )
    @super_admin_required
    def get(self, request):
        """
        User list api / Get user by id
        """
        # python 3.8
        # if user_id := request.GET.get("id"):
        user_id = request.GET.get("id")
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return self.error("User does not exist")
            return self.success(UserAdminSerializer(user).data)

        user = User.objects.all().order_by("-create_time")

        # python 3.8
        # if keyword := request.GET.get("keyword", None)
        keyword = request.GET.get("keyword", None)
        if keyword:
            user = user.filter(Q(username__icontains=keyword) |
                               Q(userprofile__real_name__icontains=keyword) |
                               Q(email__icontains=keyword))
        return self.success(self.paginate_data(request, user, UserAdminSerializer))
        # TODO: DRF Pagination(PageNumberPagination)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="id", in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="unique user id",
            ),
        ],
        operation_description="Delete User"
    )
    @super_admin_required
    def delete(self, request):
        id = request.GET.get("id")
        if not id:
            return self.error("Invalid Parameter, id is required")
        ids = id.split(",")
        if str(request.user.id) in ids:
            return self.error("Current user can not be deleted")
        User.objects.filter(id__in=ids).delete()
        return self.success()


class GenerateUserAPI(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="file_id", in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="unique file_id",
                required=True
            ),
        ],
        operation_description="Get User Excel"
    )
    @super_admin_required
    def get(self, request):
        """
        download users excel
        """
        file_id = request.GET.get("file_id")
        if not file_id:
            return self.error("Invalid Parameter, file_id is required")
        if not re.match(r"^[a-zA-Z0-9]+$", file_id):
            return self.error("Illegal file_id")
        file_path = f"/tmp/{file_id}.xlsx"
        if not os.path.isfile(file_path):
            return self.error("File does not exist")
        with open(file_path, "rb") as f:
            raw_data = f.read()
        os.remove(file_path)
        response = HttpResponse(raw_data)
        response["Content-Disposition"] = "attachment; filename=users.xlsx"
        response["Content-Type"] = "application/xlsx"
        return response

    @swagger_auto_schema(
        request_body=(GenerateUserSerializer),
        operation_description="Generate User"
    )
    @validate_serializer(GenerateUserSerializer)
    @super_admin_required
    def post(self, request):
        """
        Generate User
        """
        data = request.data
        number_max_length = max(len(str(data["number_from"])), len(str(data["number_to"])))
        if number_max_length + len(data["prefix"]) + len(data["suffix"]) > 32:
            return self.error("Username should not more than 32 characters")
        if data["number_from"] > data["number_to"]:
            return self.error("Start number must be lower than end number")

        file_id = rand_str(8)
        filename = f"/tmp/{file_id}.xlsx"
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()
        worksheet.set_column("A:B", 20)
        worksheet.write("A1", "Username")
        worksheet.write("B1", "Password")
        i = 1

        user_list = []
        for number in range(data["number_from"], data["number_to"] + 1):
            raw_password = rand_str(data["password_length"])
            user = User(username=f"{data['prefix']}{number}{data['suffix']}", password=make_password(raw_password))
            user.raw_password = raw_password
            user_list.append(user)

        try:
            with transaction.atomic():
                ret = User.objects.bulk_create(user_list)
                UserProfile.objects.bulk_create([UserProfile(user=user) for user in ret])
                for item in user_list:
                    worksheet.write_string(i, 0, item.username)
                    worksheet.write_string(i, 1, item.raw_password)
                    i += 1
                workbook.close()
                return self.success({"file_id": file_id})
        except IntegrityError as e:
            # Extract detail from exception message
            #    duplicate key value violates unique constraint "user_username_key"
            #    DETAIL:  Key (username)=(root11) already exists.
            return self.error(str(e).split("\n")[1])
