# -------------------------------------------------------------------
# FILE: models.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# SQLAlchemy ORM models for the merged SolomonV3 database.
# -------------------------------------------------------------------

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from solomon_core.db import Base


def utc_now() -> datetime:
    """Return the canonical database timestamp as timezone-aware UTC."""

    return datetime.now(timezone.utc)


def new_opaque_id() -> str:
    """Return a stable opaque identifier for externally referenced records."""

    return uuid.uuid4().hex


GROUP_LIBRARY_SCOPE = "group_library"
GROUP_CONTROLLED_CUSTODY_MODE = "group_controlled"
GROUP_FILE_PERMISSION_POLICY_VERSION = "group_file_permissions_v1"
GROUP_MEMBERSHIP_INVITATION_CONTRACT = "group_membership_invitation_v1"
GROUP_AUDIT_EVENT_CONTRACT = "group_audit_event_v1"
GROUP_FILE_ACCESS_GRANT_TYPE = "group"


# ===============================================================
# USER / GROUP SHELL
# ===============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    role = Column(String(32), default="user", nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    must_change_password = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    temp_password_issued_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_ip = Column(String(45), nullable=True)
    last_login_ip_version = Column(String(8), nullable=True)
    last_login_ip_country = Column(String(2), nullable=True)
    last_login_ip_region = Column(String(64), nullable=True)
    last_login_ip_city = Column(String(64), nullable=True)
    last_login_ip_source = Column(String(16), nullable=True)

    account_package = Column(
        String(32),
        default="personal",
        nullable=False,
        index=True,
    )
    account_package_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    plan_status = Column(
        String(32),
        default="free",
        nullable=False,
        index=True,
    )
    stripe_customer_id = Column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_subscription_id = Column(
        String(255),
        unique=True,
        nullable=True,
    )
    trial_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    trial_ends_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_limit = Column(Integer, nullable=True)
    reviews_used = Column(Integer, default=0, nullable=False)
    billing_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    files = relationship(
        "FileRegistry",
        back_populates="uploader",
        cascade="all, delete-orphan",
    )

    organizations_created = relationship(
        "Organization",
        back_populates="created_by",
        foreign_keys="Organization.created_by_user_id",
    )

    organization_memberships = relationship(
        "OrganizationMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationMembership.user_id",
    )

    organization_groups_created = relationship(
        "OrganizationGroup",
        back_populates="created_by",
        foreign_keys="OrganizationGroup.created_by_user_id",
    )

    organization_group_memberships = relationship(
        "OrganizationGroupMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationGroupMembership.user_id",
    )

    organization_group_memberships_added = relationship(
        "OrganizationGroupMembership",
        back_populates="added_by_user",
        foreign_keys="OrganizationGroupMembership.added_by_user_id",
    )

    received_file_grants = relationship(
        "FileAccessGrant",
        back_populates="granted_to_user",
        cascade="all, delete-orphan",
        foreign_keys="FileAccessGrant.granted_to_user_id",
    )

    issued_file_grants = relationship(
        "FileAccessGrant",
        back_populates="granted_by_user",
        foreign_keys="FileAccessGrant.granted_by_user_id",
    )

    revoked_file_grants = relationship(
        "FileAccessGrant",
        back_populates="revoked_by_user",
        foreign_keys="FileAccessGrant.revoked_by_user_id",
    )

    issued_group_file_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="granted_by_user",
        foreign_keys="FileGroupAccessGrant.granted_by_user_id",
    )

    revoked_group_file_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="revoked_by_user",
        foreign_keys="FileGroupAccessGrant.revoked_by_user_id",
    )

    file_authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="actor_user",
        foreign_keys="FileAuthorizationDecision.actor_user_id",
    )

    bid_review_records = relationship(
        "BidReviewRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    workspace_artifacts = relationship(
        "WorkspaceArtifact",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    review_sets = relationship(
        "ReviewSet",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    solomon_ai_conversations = relationship(
        "SolomonAIConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    issued_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="invited_by_user",
        foreign_keys="OrganizationInvitation.invited_by_user_id",
    )

    accepted_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="accepted_by_user",
        foreign_keys="OrganizationInvitation.accepted_by_user_id",
    )

    revoked_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="revoked_by_user",
        foreign_keys="OrganizationInvitation.revoked_by_user_id",
    )

    organization_audit_events_as_actor = relationship(
        "OrganizationAuditEvent",
        back_populates="actor_user",
        foreign_keys="OrganizationAuditEvent.actor_user_id",
    )

    organization_audit_events_as_target = relationship(
        "OrganizationAuditEvent",
        back_populates="target_user",
        foreign_keys="OrganizationAuditEvent.target_user_id",
    )


class FileRegistry(Base):
    __tablename__ = "file_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    random_name = Column(String(64), unique=True, nullable=False)
    original_name = Column(String(255), nullable=False)
    extension = Column(String(16))
    path = Column(String(512), nullable=False)
    meta = Column(JSON)
    upload_time = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    size_bytes = Column(Integer)
    checksum = Column(String(64))

    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    classification = Column(
        String(32),
        default="internal",
        nullable=False,
        index=True,
    )
    version_number = Column(
        Integer,
        default=1,
        nullable=False,
    )
    archived_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    uploader_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    uploader = relationship(
        "User",
        back_populates="files",
    )

    artifact_sources = relationship(
        "WorkspaceArtifactSource",
        back_populates="file",
    )

    solomon_ai_conversation_sources = relationship(
        "SolomonAIConversationSource",
        back_populates="file",
    )

    organization_custodies = relationship(
        "OrganizationFileCustody",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    access_grants = relationship(
        "FileAccessGrant",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    group_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="file",
    )

    @property
    def display_name(self) -> str:
        return self.original_name

    @property
    def filename(self) -> str:
        return self.original_name


# ===============================================================
# GROUP ACCOUNT / MEMBERSHIP / DOCUMENT AUTHORITY
# ===============================================================
# NOTE:
# These ORM class and table names remain as a temporary database bridge while
# the active product namespace moves to People and Groups. New code may import
# the canonical aliases near the bottom of this file, while the later MySQL
# migration can rename physical tables and columns deliberately.
class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(
        String(64),
        primary_key=True,
        default=new_opaque_id,
    )
    name = Column(String(255), nullable=False)
    slug = Column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    legal_name = Column(
        String(255),
        nullable=True,
    )
    verified_domain = Column(
        String(255),
        nullable=True,
        index=True,
    )
    verification_status = Column(
        String(32),
        default="unverified",
        nullable=False,
        index=True,
    )
    verification_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    authorization_policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    default_file_visibility = Column(
        String(64),
        default=GROUP_LIBRARY_SCOPE,
        nullable=False,
        index=True,
    )
    ai_query_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    suspended_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    created_by = relationship(
        "User",
        back_populates="organizations_created",
        foreign_keys=[created_by_user_id],
    )

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationMembership.created_at",
    )

    file_custodies = relationship(
        "OrganizationFileCustody",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationFileCustody.created_at",
    )

    file_access_grants = relationship(
        "FileAccessGrant",
        back_populates="organization",
    )

    groups = relationship(
        "OrganizationGroup",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationGroup.created_at",
    )

    group_file_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="organization",
    )

    authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="organization",
    )

    conversation_contexts = relationship(
        "SolomonAIConversationOrganizationContext",
        back_populates="organization",
    )

    invitations = relationship(
        "OrganizationInvitation",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationInvitation.created_at",
    )

    audit_events = relationship(
        "OrganizationAuditEvent",
        back_populates="organization",
        order_by="OrganizationAuditEvent.created_at",
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_membership",
        ),
        Index(
            "ix_organization_membership_user_status",
            "user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_primary = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    invited_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    joined_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="memberships",
    )
    user = relationship(
        "User",
        back_populates="organization_memberships",
        foreign_keys=[user_id],
    )
    invited_by_user = relationship(
        "User",
        foreign_keys=[invited_by_user_id],
    )

    invitations = relationship(
        "OrganizationInvitation",
        back_populates="membership",
        foreign_keys="OrganizationInvitation.membership_id",
    )


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        Index(
            "ix_organization_invitation_org_email_status",
            "organization_id",
            "normalized_email",
            "status",
        ),
        Index(
            "ix_organization_invitation_email_status",
            "normalized_email",
            "status",
        ),
        Index(
            "ix_organization_invitation_token_status",
            "token_hash",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    invitation_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    membership_id = Column(
        Integer,
        ForeignKey(
            "organization_memberships.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    email = Column(String(255), nullable=False)
    normalized_email = Column(
        String(255),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    token_hash = Column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )
    invitation_contract = Column(
        String(128),
        default=GROUP_MEMBERSHIP_INVITATION_CONTRACT,
        nullable=False,
    )

    invited_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    accepted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    organization = relationship(
        "Organization",
        back_populates="invitations",
    )
    membership = relationship(
        "OrganizationMembership",
        back_populates="invitations",
        foreign_keys=[membership_id],
    )
    invited_by_user = relationship(
        "User",
        back_populates="issued_organization_invitations",
        foreign_keys=[invited_by_user_id],
    )
    accepted_by_user = relationship(
        "User",
        back_populates="accepted_organization_invitations",
        foreign_keys=[accepted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_organization_invitations",
        foreign_keys=[revoked_by_user_id],
    )


class OrganizationAuditEvent(Base):
    __tablename__ = "organization_audit_events"
    __table_args__ = (
        Index(
            "ix_organization_audit_org_event_created",
            "organization_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_actor_event_created",
            "actor_user_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_target_event_created",
            "target_user_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_request_created",
            "request_id",
            "created_at",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    event_type = Column(
        String(128),
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=GROUP_AUDIT_EVENT_CONTRACT,
        nullable=False,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    target_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    target_email = Column(
        String(255),
        nullable=True,
        index=True,
    )
    invitation_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    membership_id = Column(
        Integer,
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    role_before = Column(
        String(32),
        nullable=True,
    )
    role_after = Column(
        String(32),
        nullable=True,
    )
    decision = Column(
        String(32),
        default="recorded",
        nullable=False,
        index=True,
    )
    reason_code = Column(
        String(128),
        nullable=True,
        index=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    source = Column(
        String(128),
        nullable=True,
        index=True,
    )
    details_json = Column(
        JSON,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="audit_events",
    )
    actor_user = relationship(
        "User",
        back_populates="organization_audit_events_as_actor",
        foreign_keys=[actor_user_id],
    )
    target_user = relationship(
        "User",
        back_populates="organization_audit_events_as_target",
        foreign_keys=[target_user_id],
    )
    file = relationship(
        "FileRegistry",
    )


class OrganizationGroup(Base):
    __tablename__ = "organization_groups"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_organization_group_slug",
        ),
        Index(
            "ix_organization_group_org_status",
            "organization_id",
            "status",
        ),
    )

    group_id = Column(
        String(64),
        primary_key=True,
        default=new_opaque_id,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    slug = Column(
        String(128),
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="groups",
    )
    created_by = relationship(
        "User",
        back_populates="organization_groups_created",
        foreign_keys=[created_by_user_id],
    )
    memberships = relationship(
        "OrganizationGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="OrganizationGroupMembership.created_at",
    )
    file_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class OrganizationGroupMembership(Base):
    __tablename__ = "organization_group_memberships"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_organization_group_membership",
        ),
        Index(
            "ix_organization_group_membership_user_status",
            "user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    added_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    joined_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    group = relationship(
        "OrganizationGroup",
        back_populates="memberships",
    )
    user = relationship(
        "User",
        back_populates="organization_group_memberships",
        foreign_keys=[user_id],
    )
    added_by_user = relationship(
        "User",
        back_populates="organization_group_memberships_added",
        foreign_keys=[added_by_user_id],
    )


class OrganizationFileCustody(Base):
    __tablename__ = "organization_file_custody"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "file_registry_id",
            name="uq_organization_file_custody",
        ),
        Index(
            "ix_organization_file_custody_org_status",
            "organization_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    custody_mode = Column(
        String(64),
        default=GROUP_CONTROLLED_CUSTODY_MODE,
        nullable=False,
        index=True,
    )
    library_scope = Column(
        String(64),
        default=GROUP_LIBRARY_SCOPE,
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    classification = Column(
        String(32),
        default="internal",
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    added_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="file_custodies",
    )
    file = relationship(
        "FileRegistry",
        back_populates="organization_custodies",
    )
    added_by_user = relationship(
        "User",
        foreign_keys=[added_by_user_id],
    )


class FileAccessGrant(Base):
    __tablename__ = "file_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            "granted_to_user_id",
            name="uq_file_access_grant_recipient",
        ),
        Index(
            "ix_file_access_grant_recipient_status",
            "granted_to_user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    granted_to_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default="direct_user",
        nullable=False,
        index=True,
    )
    permission = Column(
        String(32),
        default="view",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(
        String(255),
        nullable=True,
    )

    file = relationship(
        "FileRegistry",
        back_populates="access_grants",
    )
    organization = relationship(
        "Organization",
        back_populates="file_access_grants",
    )
    granted_to_user = relationship(
        "User",
        back_populates="received_file_grants",
        foreign_keys=[granted_to_user_id],
    )
    granted_by_user = relationship(
        "User",
        back_populates="issued_file_grants",
        foreign_keys=[granted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_file_grants",
        foreign_keys=[revoked_by_user_id],
    )


class FileGroupAccessGrant(Base):
    __tablename__ = "file_group_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            "group_id",
            name="uq_file_group_access_grant_recipient",
        ),
        Index(
            "ix_file_group_access_grant_group_status",
            "group_id",
            "status",
        ),
        Index(
            "ix_file_group_access_grant_org_status",
            "organization_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default=GROUP_FILE_ACCESS_GRANT_TYPE,
        nullable=False,
        index=True,
    )
    permission = Column(
        String(32),
        default="view",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(
        String(255),
        nullable=True,
    )

    file = relationship(
        "FileRegistry",
        back_populates="group_access_grants",
    )
    organization = relationship(
        "Organization",
        back_populates="group_file_access_grants",
    )
    group = relationship(
        "OrganizationGroup",
        back_populates="file_access_grants",
    )
    granted_by_user = relationship(
        "User",
        back_populates="issued_group_file_grants",
        foreign_keys=[granted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_group_file_grants",
        foreign_keys=[revoked_by_user_id],
    )


class FileAuthorizationDecision(Base):
    __tablename__ = "file_authorization_decisions"
    __table_args__ = (
        Index(
            "ix_file_authorization_actor_action_created",
            "actor_user_id",
            "action",
            "created_at",
        ),
        Index(
            "ix_file_authorization_resource_action_created",
            "file_registry_id",
            "action",
            "created_at",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    case_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    manifest_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    action = Column(
        String(32),
        nullable=False,
        index=True,
    )
    decision = Column(
        String(16),
        nullable=False,
        index=True,
    )
    reason_code = Column(
        String(64),
        nullable=False,
        index=True,
    )
    access_scope = Column(
        String(64),
        nullable=True,
        index=True,
    )
    permission = Column(
        String(32),
        nullable=True,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    details_json = Column(
        JSON,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    actor_user = relationship(
        "User",
        back_populates="file_authorization_decisions",
        foreign_keys=[actor_user_id],
    )
    organization = relationship(
        "Organization",
        back_populates="authorization_decisions",
    )
    file = relationship(
        "FileRegistry",
        back_populates="authorization_decisions",
    )


class BidReviewRecord(Base):
    __tablename__ = "bid_review_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    review_title = Column(String(255), nullable=False)
    review_mode = Column(
        String(32),
        nullable=False,
        index=True,
    )
    document_names = Column(Text, nullable=True)

    risk_level = Column(
        String(64),
        nullable=True,
        index=True,
    )
    scope_completeness = Column(
        String(64),
        nullable=True,
        index=True,
    )
    report_html = Column(Text, nullable=True)
    structured_payload = Column(Text, nullable=True)

    status = Column(
        String(32),
        default="completed",
        nullable=False,
        index=True,
    )
    analysis_version = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="bid_review_records",
    )


# ===============================================================
# WORKSPACE ARTIFACTS / SAVED REVIEWS
# ===============================================================
class WorkspaceArtifact(Base):
    __tablename__ = "workspace_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_type = Column(
        String(64),
        default="review",
        nullable=False,
        index=True,
    )
    report_type = Column(
        String(128),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)

    status = Column(
        String(32),
        default="completed",
        nullable=False,
        index=True,
    )
    risk_level = Column(
        String(64),
        nullable=True,
        index=True,
    )
    scope_completeness = Column(
        String(64),
        nullable=True,
        index=True,
    )
    confidence_level = Column(
        String(64),
        nullable=True,
        index=True,
    )

    operation_key = Column(
        String(128),
        nullable=True,
        index=True,
    )
    job_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    analysis_version = Column(String(64), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="workspace_artifacts",
    )

    sources = relationship(
        "WorkspaceArtifactSource",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactSource.source_order",
    )

    sections = relationship(
        "WorkspaceArtifactSection",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactSection.section_order",
    )

    findings = relationship(
        "WorkspaceArtifactFinding",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactFinding.sort_order",
    )

    audit_payloads = relationship(
        "WorkspaceArtifactAuditPayload",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )

    review_set_items = relationship(
        "ReviewSetItem",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class WorkspaceArtifactSource(Base):
    __tablename__ = "workspace_artifact_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_document_id = Column(
        String(128),
        nullable=True,
        index=True,
    )
    source_name = Column(String(255), nullable=False)
    source_type = Column(
        String(64),
        default="document",
        nullable=False,
        index=True,
    )
    source_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="sources",
    )
    file = relationship(
        "FileRegistry",
        back_populates="artifact_sources",
    )


class WorkspaceArtifactSection(Base):
    __tablename__ = "workspace_artifact_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    section_key = Column(
        String(128),
        nullable=True,
        index=True,
    )
    section_title = Column(String(255), nullable=False)
    section_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    body_html = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="sections",
    )


class WorkspaceArtifactFinding(Base):
    __tablename__ = "workspace_artifact_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    source_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifact_sources.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    finding_type = Column(
        String(128),
        nullable=True,
        index=True,
    )
    severity = Column(
        String(64),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    finding_text = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    source_document_id = Column(
        String(128),
        nullable=True,
        index=True,
    )
    page_number = Column(Integer, nullable=True)
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="findings",
    )
    source = relationship("WorkspaceArtifactSource")


class ReviewSet(Base):
    __tablename__ = "review_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="review_sets",
    )

    items = relationship(
        "ReviewSetItem",
        back_populates="review_set",
        cascade="all, delete-orphan",
        order_by="ReviewSetItem.sort_order",
    )


class ReviewSetItem(Base):
    __tablename__ = "review_set_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_set_id = Column(
        Integer,
        ForeignKey(
            "review_sets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    review_set = relationship(
        "ReviewSet",
        back_populates="items",
    )
    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="review_set_items",
    )


class WorkspaceArtifactAuditPayload(Base):
    __tablename__ = "workspace_artifact_audit_payloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    payload_kind = Column(
        String(128),
        nullable=False,
        index=True,
    )
    payload_json = Column(JSON, nullable=True)
    payload_text = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="audit_payloads",
    )


# ===============================================================
# SOLOMONAI CONVERSATION PERSISTENCE
# ===============================================================
class SolomonAIConversation(Base):
    __tablename__ = "solomon_ai_conversations"

    conversation_id = Column(
        String(64),
        primary_key=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        default="New conversation",
        nullable=False,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    contract = Column(
        String(128),
        default="document_ai_explicit_source_session",
        nullable=False,
    )
    source_membership_contract = Column(
        String(128),
        default="solomon_ai_conversation_source_membership_v1",
        nullable=False,
    )
    operation_key = Column(
        String(128),
        default="ask_solomon_ai",
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="solomon_ai_conversations",
    )

    sources = relationship(
        "SolomonAIConversationSource",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SolomonAIConversationSource.source_order",
    )

    messages = relationship(
        "SolomonAIConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SolomonAIConversationMessage.message_order",
    )

    organization_context = relationship(
        "SolomonAIConversationOrganizationContext",
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SolomonAIConversationSource(Base):
    __tablename__ = "solomon_ai_conversation_sources"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "source_document_id",
            name="uq_solomon_ai_conversation_source",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_document_id = Column(
        String(128),
        nullable=False,
        index=True,
    )
    source_name = Column(String(255), nullable=False)
    source_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="sources",
    )
    file = relationship(
        "FileRegistry",
        back_populates="solomon_ai_conversation_sources",
    )


class SolomonAIConversationOrganizationContext(Base):
    __tablename__ = "solomon_ai_conversation_organization_context"

    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    membership_id = Column(
        Integer,
        ForeignKey(
            "organization_memberships.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    bound_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="organization_context",
    )
    organization = relationship(
        "Organization",
        back_populates="conversation_contexts",
    )
    membership = relationship(
        "OrganizationMembership",
    )
    bound_by_user = relationship(
        "User",
        foreign_keys=[bound_by_user_id],
    )


class SolomonAIConversationMessage(Base):
    __tablename__ = "solomon_ai_conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "message_order",
            name="uq_solomon_ai_conversation_message_order",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role = Column(
        String(32),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    bridge = Column(Text, nullable=True)
    suggestions = Column(JSON, nullable=True)
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    message_order = Column(Integer, nullable=False)
    status = Column(
        String(32),
        default="complete",
        nullable=False,
        index=True,
    )
    packet_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="messages",
    )


# ===============================================================
# INVESTIGATOR CASEFILES / GOVERNANCE
# ===============================================================
class InvestigatorCaseFile(Base):
    __tablename__ = "investigator_case_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(128), nullable=False, index=True)
    route = Column(String(128), nullable=True, index=True)
    packet_type = Column(String(128), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(String(64), nullable=True, index=True)
    conversation_id = Column(String(64), nullable=True, index=True)
    document_ids_json = Column(JSON, nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    decision_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


# ===============================================================
# AUTONOMY / GOVERNANCE / LEARNING LOGS
# ===============================================================
class AutonomyLog(Base):
    __tablename__ = "autonomy_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    task_type = Column(String(128), index=True)
    description = Column(Text)
    status = Column(String(64), index=True)
    score = Column(Float)
    notes = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class AutonomyStats(Base):
    __tablename__ = "autonomy_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True)
    tasks_completed = Column(Integer)
    tasks_failed = Column(Integer)
    avg_score = Column(Float)
    best_task = Column(Text)
    weakest_area = Column(Text)
    recommendations = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class AutonomyState(Base):
    __tablename__ = "autonomy_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(String(64), unique=True, index=True)
    agent_id = Column(String(128), index=True)
    run_id = Column(String(64), index=True)
    task_type = Column(String(128), index=True)
    capability_mode = Column(String(64))
    current_prompt = Column(Text)
    context_json = Column(JSON)
    notes_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class SkillRegistry(Base):
    __tablename__ = "skill_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_key = Column(String(128), unique=True, nullable=False, index=True)
    skill_name = Column(String(255), nullable=False)
    skill_category = Column(String(128), nullable=False, index=True)
    description = Column(Text)
    owner_agent = Column(String(128), index=True)
    version = Column(String(64), default="1.0.0")
    status = Column(String(64), default="active", index=True)
    review_cadence = Column(String(64))
    last_reviewed_at = Column(DateTime(timezone=True))
    next_review_due_at = Column(DateTime(timezone=True))
    performance_score = Column(Float)
    usage_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    governance_notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class SkillUpgradeLog(Base):
    __tablename__ = "skill_upgrade_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upgrade_id = Column(String(64), unique=True, index=True)
    skill_key = Column(String(128), nullable=False, index=True)
    from_version = Column(String(64))
    to_version = Column(String(64))
    status = Column(String(64), default="proposed", index=True)
    trigger = Column(String(128))
    rationale = Column(Text)
    diff_summary = Column(Text)
    test_results = Column(JSON)
    reviewer = Column(String(128))
    approved_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    rollback_id = Column(String(64))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(64), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(128))
    feature = Column(String(128), index=True)
    message = Column(Text)
    rating = Column(Integer)
    category = Column(String(128))
    raw_json = Column(JSON)
    status = Column(String(64), default="new", index=True)
    handled_by = Column(String(128))
    handled_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    correction_id = Column(String(64), unique=True, index=True)
    source_feature = Column(String(128), index=True)
    issue_type = Column(String(128))
    user_feedback_id = Column(String(64), index=True)
    bad_output_hash = Column(String(64))
    corrected_payload = Column(JSON)
    correction_summary = Column(Text)
    status = Column(String(64), default="pending", index=True)
    approved_by = Column(String(128))
    approved_at = Column(DateTime(timezone=True))
    applied_in_version = Column(String(64))
    notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class HfloPendingUpgrade(Base):
    __tablename__ = "hflo_pending_upgrades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_name = Column(String(255), nullable=False, index=True)
    current_version = Column(String(64))
    latest_version = Column(String(64))
    status = Column(String(64), default="pending", index=True)
    reason = Column(Text)
    source = Column(String(255))
    release_url = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class PlannerPatchLog(Base):
    __tablename__ = "planner_patch_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patch_id = Column(String(64), unique=True, index=True)
    source = Column(String(128), index=True)
    target_file = Column(String(512), index=True)
    summary = Column(Text)
    patch_content = Column(Text)
    patch_type = Column(String(64))
    risk_level = Column(String(64))
    status = Column(String(64), default="proposed", index=True)
    approved_by = Column(String(128))
    applied_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    rollback_id = Column(String(64))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class PlannerRollbackLog(Base):
    __tablename__ = "planner_rollback_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rollback_id = Column(String(64), unique=True, index=True)
    patch_id = Column(String(64), index=True)
    target_file = Column(String(512), index=True)
    reason = Column(Text)
    restored_content = Column(Text)
    status = Column(String(64), default="pending", index=True)
    performed_by = Column(String(128))
    performed_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class PlanLog(Base):
    __tablename__ = "plan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), unique=True, index=True)
    title = Column(String(255), nullable=False)
    goal = Column(Text)
    risk_level = Column(String(64))
    status = Column(String(64), default="planned", index=True)
    owner = Column(String(128))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class PlanStepLog(Base):
    __tablename__ = "plan_step_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(String(64), unique=True, index=True)
    plan_id = Column(String(64), index=True)
    step_order = Column(Integer)
    title = Column(String(255))
    status = Column(String(64), default="pending", index=True)
    owner = Column(String(128))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, index=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    parent_task_id = Column(String(64), index=True)
    title = Column(String(255))
    description = Column(Text)
    task_type = Column(String(128))
    status = Column(String(64), default="pending", index=True)
    priority = Column(String(64))
    input_payload = Column(JSON)
    output_payload = Column(JSON)
    failure_reason = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), unique=True, index=True)
    task_id = Column(String(64), index=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    tool_name = Column(String(128))
    target = Column(String(512))
    status = Column(String(64), default="pending")
    error_message = Column(Text)
    result_snippet = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    metadata_json = Column(JSON)
    reasoning_type = Column(String(255))
    reasoning_source = Column(String(255))


class SecurityLog(Base):
    __tablename__ = "security_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(128))
    username = Column(String(128))
    ip_address = Column(String(64))
    user_agent = Column(Text)
    details_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


# ===============================================================
# CANONICAL PEOPLE / GROUPS MODEL ALIASES
# ===============================================================
# These aliases let new application code speak in the People/Groups namespace
# without forcing an unsafe in-place ORM/table rename before the coordinated
# MySQL migration runs. The legacy ORM names remain exported during the bridge.
Group = Organization
GroupMembership = OrganizationMembership
GroupInvitation = OrganizationInvitation
GroupAuditEvent = OrganizationAuditEvent
GroupFileCustody = OrganizationFileCustody
GroupConversationContext = SolomonAIConversationOrganizationContext


__all__ = [
    "User",
    "FileRegistry",
    "Group",
    "GroupMembership",
    "GroupInvitation",
    "GroupAuditEvent",
    "GroupFileCustody",
    "GroupConversationContext",
    "Organization",
    "OrganizationMembership",
    "OrganizationInvitation",
    "OrganizationAuditEvent",
    "OrganizationGroup",
    "OrganizationGroupMembership",
    "OrganizationFileCustody",
    "FileAccessGrant",
    "FileGroupAccessGrant",
    "FileAuthorizationDecision",
    "BidReviewRecord",
    "WorkspaceArtifact",
    "WorkspaceArtifactSource",
    "WorkspaceArtifactSection",
    "WorkspaceArtifactFinding",
    "ReviewSet",
    "ReviewSetItem",
    "WorkspaceArtifactAuditPayload",
    "SolomonAIConversation",
    "SolomonAIConversationSource",
    "SolomonAIConversationOrganizationContext",
    "SolomonAIConversationMessage",
    "InvestigatorCaseFile",
    "AutonomyLog",
    "AutonomyStats",
    "AutonomyState",
    "SkillRegistry",
    "SkillUpgradeLog",
    "Feedback",
    "Correction",
    "HfloPendingUpgrade",
    "PlannerPatchLog",
    "PlannerRollbackLog",
    "PlanLog",
    "PlanStepLog",
    "TaskHistory",
    "ExecutionLog",
    "SecurityLog",
]