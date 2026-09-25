from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import LoginEvent, Role
from apps.accounts.rbac import PERMISSIONS
from apps.core.models import AuditLog
from apps.core.testing import client_for, make_admin, make_department, make_programme, make_staff, make_student

User = get_user_model()


class LoginTests(TestCase):
    def test_login_history(self):
        make_student("stu")
        client = APIClient()
        self.assertEqual(client.post("/api/auth/token/", {"username": "stu", "password": "wrong"}).status_code, 401)
        self.assertEqual(client.post("/api/auth/token/", {"username": "stu", "password": "x"}).status_code, 200)
        events = list(LoginEvent.objects.order_by("created_at").values_list("username", "successful"))
        self.assertEqual(events, [("stu", False), ("stu", True)])
        user = User.objects.get(username="stu")
        self.assertIsNotNone(user.last_login)
        self.assertEqual(len(client_for(user).get("/api/auth/me/logins/").data), 2)


class MeTests(TestCase):
    def test_me_includes_permissions_and_profile(self):
        student = make_student(programme=make_programme(name="Computer Science"), level=200)
        data = client_for(student).get("/api/auth/me/").data
        self.assertEqual(data["permissions"], [])
        self.assertEqual(data["student_profile"]["level"], 200)
        self.assertEqual(data["student_profile"]["programme_title"], "B.Sc. Computer Science")

        bursar = make_staff(roles=["bursar"])
        data = client_for(bursar).get("/api/auth/me/").data
        self.assertEqual(data["permissions"], ["finance.manage", "finance.view", "reports.view"])
        self.assertEqual([a["role_code"] for a in data["assignments"]], ["bursar"])

    def test_names_and_ids_are_locked(self):
        student = make_student(first_name="Ada")
        client_for(student).patch("/api/auth/me/", {"first_name": "Changed", "role": "admin", "phone": "0803"})
        student.refresh_from_db()
        self.assertEqual((student.first_name, student.role, student.phone), ("Ada", "student", "0803"))

    def test_student_edits_contacts_not_academic_record(self):
        student = make_student(level=200)
        res = client_for(student).patch(
            "/api/auth/me/student-profile/",
            {
                "next_of_kin_name": "Mrs. Okafor",
                "emergency_contact_phone": "08031234567",
                "level": 400,
                "status": "graduated",
            },
        )
        self.assertEqual(res.status_code, 200)
        profile = student.student_profile
        profile.refresh_from_db()
        self.assertEqual((profile.next_of_kin_name, profile.emergency_contact_phone), ("Mrs. Okafor", "08031234567"))
        self.assertEqual((profile.level, profile.status), (200, "active"))


class RoleManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.registrar = make_staff(roles=["registrar"])
        cls.lecturer = make_staff(roles=["lecturer"])
        cls.department = make_department()

    def test_assign_scoped_role(self):
        client = client_for(self.registrar)
        hod = Role.objects.get(code="hod")
        res = client.post("/api/role-assignments/", {"user": self.lecturer.id, "role": hod.id})
        self.assertEqual(res.status_code, 400)  # HOD needs a department
        res = client.post(
            "/api/role-assignments/", {"user": self.lecturer.id, "role": hod.id, "department": self.department.id}
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(User.objects.get(pk=self.lecturer.pk).has_permission("results.approve_department"))
        self.assertTrue(AuditLog.objects.filter(action="role.assign").exists())
        student = make_student()
        self.assertEqual(
            client.post(
                "/api/role-assignments/", {"user": student.id, "role": hod.id, "department": self.department.id}
            ).status_code,
            400,
        )

    def test_edit_role_permissions(self):
        role = Role.objects.get(code="librarian")
        client = client_for(self.registrar)
        self.assertEqual(
            client.patch(f"/api/roles/{role.id}/", {"permissions": ["nope"]}, format="json").status_code, 400
        )
        res = client.patch(f"/api/roles/{role.id}/", {"permissions": ["library.manage", "reports.view"]}, format="json")
        self.assertEqual(res.data["permissions"], ["library.manage", "reports.view"])

    def test_only_role_managers(self):
        self.assertEqual(client_for(self.lecturer).get("/api/roles/").status_code, 403)
        self.assertEqual(client_for(self.lecturer).get("/api/permissions/").status_code, 403)
        self.assertEqual(len(client_for(make_admin()).get("/api/permissions/").data), len(PERMISSIONS))

    def test_directory_lists_staff_only(self):
        make_student()
        rows = client_for(self.lecturer).get("/api/directory/").data["results"]
        self.assertEqual({r["role"] for r in rows}, {"staff"})
