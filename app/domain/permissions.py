"""What each role is allowed to do.

Super Admin is not a special case inside services. The set below already
contains every permission, so a new endpoint cannot accidentally forget it.
"""

from app.domain.enums import Role


class Permission:
    MANAGE_USERS = "manage_users"
    READ_DONORS = "read_donors"
    WRITE_DONORS = "write_donors"
    READ_CAMPAIGNS = "read_campaigns"
    WRITE_CAMPAIGNS = "write_campaigns"
    READ_DONATIONS = "read_donations"
    WRITE_DONATIONS = "write_donations"
    CONFIRM_DONATIONS = "confirm_donations"
    ISSUE_RECEIPTS = "issue_receipts"
    READ_VOLUNTEERS = "read_volunteers"
    WRITE_VOLUNTEERS = "write_volunteers"
    ASSIGN_VOLUNTEERS = "assign_volunteers"
    READ_PROJECTS = "read_projects"
    WRITE_PROJECTS = "write_projects"
    APPROVE_PROJECTS = "approve_projects"
    MANAGE_TASKS = "manage_tasks"
    SUBMIT_EXPENSES = "submit_expenses"
    APPROVE_EXPENSES = "approve_expenses"
    READ_BUDGETS = "read_budgets"
    MANAGE_BUDGETS = "manage_budgets"
    READ_RESOURCES = "read_resources"
    MANAGE_RESOURCES = "manage_resources"
    READ_BENEFICIARIES = "read_beneficiaries"
    WRITE_BENEFICIARIES = "write_beneficiaries"
    READ_BENEFICIARY_SENSITIVE = "read_beneficiary_sensitive"
    RECORD_ASSISTANCE = "record_assistance"
    WRITE_IMPACT = "write_impact"
    READ_DASHBOARD = "read_dashboard"
    READ_REPORTS = "read_reports"
    READ_AUDIT = "read_audit"
    SCAN_NOTIFICATIONS = "scan_notifications"


ALL_PERMISSIONS = {
    value for name, value in vars(Permission).items() if name.isupper()
}

_MANAGER = {
    Permission.READ_DONORS,
    Permission.WRITE_DONORS,
    Permission.READ_CAMPAIGNS,
    Permission.WRITE_CAMPAIGNS,
    Permission.READ_DONATIONS,
    Permission.WRITE_DONATIONS,
    Permission.CONFIRM_DONATIONS,
    Permission.ISSUE_RECEIPTS,
    Permission.READ_VOLUNTEERS,
    Permission.WRITE_VOLUNTEERS,
    Permission.ASSIGN_VOLUNTEERS,
    Permission.READ_PROJECTS,
    Permission.WRITE_PROJECTS,
    Permission.APPROVE_PROJECTS,
    Permission.MANAGE_TASKS,
    Permission.SUBMIT_EXPENSES,
    Permission.READ_BUDGETS,
    Permission.READ_RESOURCES,
    Permission.MANAGE_RESOURCES,
    Permission.READ_BENEFICIARIES,
    Permission.WRITE_BENEFICIARIES,
    Permission.READ_BENEFICIARY_SENSITIVE,
    Permission.RECORD_ASSISTANCE,
    Permission.WRITE_IMPACT,
    Permission.READ_DASHBOARD,
    Permission.READ_REPORTS,
    Permission.READ_AUDIT,
    Permission.SCAN_NOTIFICATIONS,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.SUPER_ADMIN.value: set(ALL_PERMISSIONS),
    Role.NGO_MANAGER.value: set(_MANAGER),
    Role.FINANCE_OFFICER.value: {
        Permission.READ_DONORS,
        Permission.READ_CAMPAIGNS,
        Permission.READ_DONATIONS,
        Permission.WRITE_DONATIONS,
        Permission.CONFIRM_DONATIONS,
        Permission.ISSUE_RECEIPTS,
        Permission.READ_PROJECTS,
        Permission.SUBMIT_EXPENSES,
        Permission.APPROVE_EXPENSES,
        Permission.READ_BUDGETS,
        Permission.MANAGE_BUDGETS,
        Permission.READ_RESOURCES,
        Permission.READ_BENEFICIARIES,
        Permission.READ_DASHBOARD,
        Permission.READ_REPORTS,
        Permission.READ_AUDIT,
    },
    Role.VOLUNTEER_COORDINATOR.value: {
        Permission.READ_CAMPAIGNS,
        Permission.READ_VOLUNTEERS,
        Permission.WRITE_VOLUNTEERS,
        Permission.ASSIGN_VOLUNTEERS,
        Permission.READ_PROJECTS,
        Permission.MANAGE_TASKS,
        Permission.READ_RESOURCES,
        Permission.MANAGE_RESOURCES,
        Permission.READ_BENEFICIARIES,
        Permission.WRITE_BENEFICIARIES,
        Permission.READ_BENEFICIARY_SENSITIVE,
        Permission.RECORD_ASSISTANCE,
        Permission.READ_DASHBOARD,
        Permission.READ_REPORTS,
        Permission.SCAN_NOTIFICATIONS,
    },
    Role.VOLUNTEER.value: {
        Permission.READ_CAMPAIGNS,
        Permission.READ_PROJECTS,
        Permission.RECORD_ASSISTANCE,
    },
    Role.DONOR.value: {
        Permission.READ_CAMPAIGNS,
        Permission.READ_DONATIONS,
    },
}


def role_has(role: str, permission: str) -> bool:
    key = role.value if isinstance(role, Role) else role
    return permission in ROLE_PERMISSIONS.get(key, set())
