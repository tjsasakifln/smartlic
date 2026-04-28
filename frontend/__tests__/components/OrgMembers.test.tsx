/**
 * RBAC-ORG-001 (AC14) — RoleControls visibility matrix.
 *
 * Asserts the conditional UI rules from the story:
 * - role badge always rendered
 * - role-change dropdown only when current user is owner AND target is not self
 * - transfer-ownership button only when current user is owner AND target is non-owner non-self
 * - remove button: owner can remove anyone; member/viewer can only remove themselves
 */

import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import RoleControls, {
  RoleBadge,
  type OrgRole,
} from "@/components/organizations/RoleControls";

const noop = () => undefined;

interface Member {
  user_id: string;
  email?: string;
  role: OrgRole;
}

function setup(opts: {
  member: Member;
  currentUserRole: OrgRole;
  currentUserId: string;
}) {
  return render(
    <RoleControls
      member={opts.member}
      currentUserRole={opts.currentUserRole}
      currentUserId={opts.currentUserId}
      onRoleChange={noop}
      onRemove={noop}
      onTransferOwnership={noop}
    />
  );
}

describe("RoleBadge", () => {
  it.each<OrgRole>(["owner", "member", "viewer"])(
    "renders accessible badge for %s",
    (role) => {
      render(<RoleBadge role={role} />);
      const el = screen.getByTestId(`role-badge-${role}`);
      expect(el).toBeInTheDocument();
      expect(el).toHaveAttribute("role", "status");
      expect(el).toHaveAttribute("aria-label", expect.stringContaining("Papel:"));
    }
  );
});

describe("RoleControls — owner viewing other members", () => {
  const owner: Member = { user_id: "u-owner", email: "owner@x.com", role: "owner" };
  const member: Member = { user_id: "u-member", email: "m@x.com", role: "member" };

  it("shows role-change dropdown for non-self members", () => {
    setup({
      member: member,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(screen.getByTestId(`role-select-${member.user_id}`)).toBeInTheDocument();
  });

  it("shows transfer-ownership button for non-owner members", () => {
    setup({
      member: member,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(
      screen.getByTestId(`transfer-ownership-${member.user_id}`)
    ).toBeInTheDocument();
  });

  it("shows remove button for non-self members", () => {
    setup({
      member: member,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(screen.getByTestId(`remove-${member.user_id}`)).toBeInTheDocument();
  });

  it("does NOT show transfer-ownership button when target is also owner", () => {
    const otherOwner: Member = { user_id: "u-co-owner", role: "owner" };
    setup({
      member: otherOwner,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(
      screen.queryByTestId(`transfer-ownership-${otherOwner.user_id}`)
    ).not.toBeInTheDocument();
  });
});

describe("RoleControls — owner viewing themselves", () => {
  const owner: Member = { user_id: "u-owner", email: "owner@x.com", role: "owner" };

  it("does NOT show role-change dropdown for self", () => {
    setup({
      member: owner,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(
      screen.queryByTestId(`role-select-${owner.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("does NOT show transfer-ownership button for self", () => {
    setup({
      member: owner,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(
      screen.queryByTestId(`transfer-ownership-${owner.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("DOES show remove (self-leave) button", () => {
    setup({
      member: owner,
      currentUserRole: "owner",
      currentUserId: owner.user_id,
    });
    expect(screen.getByTestId(`remove-${owner.user_id}`)).toBeInTheDocument();
  });
});

describe("RoleControls — plain member viewing", () => {
  const me: Member = { user_id: "u-me", email: "me@x.com", role: "member" };
  const other: Member = { user_id: "u-other", email: "o@x.com", role: "member" };

  it("does NOT show role-change dropdown when not owner", () => {
    setup({ member: other, currentUserRole: "member", currentUserId: me.user_id });
    expect(
      screen.queryByTestId(`role-select-${other.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("does NOT show transfer-ownership when not owner", () => {
    setup({ member: other, currentUserRole: "member", currentUserId: me.user_id });
    expect(
      screen.queryByTestId(`transfer-ownership-${other.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("does NOT show remove button for someone else when current user is plain member", () => {
    setup({ member: other, currentUserRole: "member", currentUserId: me.user_id });
    expect(
      screen.queryByTestId(`remove-${other.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("DOES show self-leave button when target is themselves", () => {
    setup({ member: me, currentUserRole: "member", currentUserId: me.user_id });
    expect(screen.getByTestId(`remove-${me.user_id}`)).toBeInTheDocument();
  });
});

describe("RoleControls — viewer (read-only role)", () => {
  const viewer: Member = { user_id: "u-viewer", email: "v@x.com", role: "viewer" };
  const other: Member = { user_id: "u-other", email: "o@x.com", role: "member" };

  it("viewer cannot change anyone's role (no dropdown)", () => {
    setup({ member: other, currentUserRole: "viewer", currentUserId: viewer.user_id });
    expect(
      screen.queryByTestId(`role-select-${other.user_id}`)
    ).not.toBeInTheDocument();
  });

  it("viewer can self-leave", () => {
    setup({ member: viewer, currentUserRole: "viewer", currentUserId: viewer.user_id });
    expect(screen.getByTestId(`remove-${viewer.user_id}`)).toBeInTheDocument();
  });
});
