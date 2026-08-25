import { Link, NavLink, Outlet } from "react-router-dom";
import { Show, SignInButton, SignOutButton, UserButton, useAuth } from "@clerk/react";
import { Button } from "../ui/Button";

//Nav bar + routed page below it. Kept minimal so the content carries the page
export function AppShell() {
  const { isLoaded } = useAuth();

  if (!isLoaded) return null;

  // h-screen, not min-h-screen: `flex-1` on <main> only bounds anything if the
  // container has a definite height. With min-h-screen the shell grew to fit
  // its content instead, so the reading view's scroll panes had no ceiling and
  // the PDF stretched down the page rather than scrolling inside its pane.
  // <main> is the page scroll container; the reading view fills it exactly.
  return (
    <div className="h-screen flex flex-col bg-bg">
      <header className="shrink-0 border-b border-border bg-surface">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-serif text-xl text-text-primary">
              PaperTrail
            </Link>
            <Show when="signed-in">
              <nav className="flex items-center gap-4 text-sm">
                <NavItem to="/">Home</NavItem>
                <NavItem to="/library">Library</NavItem>
              </nav>
            </Show>
          </div>

          <Show when="signed-out">
            <SignInButton>
              <Button variant="primary" size="sm">
                Sign in
              </Button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <div className="flex items-center gap-3">
              <UserButton />
              <SignOutButton>
                <Button variant="ghost" size="sm">
                  Sign out
                </Button>
              </SignOutButton>
            </div>
          </Show>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-y-auto">
        <Outlet />
      </main>

      <footer className="shrink-0 border-t border-border bg-surface">
        <div className="max-w-6xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p className="text-xs text-text-muted">Created by Gauri Agrawal · 2026</p>
          <p className="text-xs text-text-muted">
            Still in development — thanks for your patience with the rough edges :)
          </p>
        </div>
      </footer>
    </div>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      // `end` so "/" isn't treated as active on every nested route.
      end={to === "/"}
      className={({ isActive }) =>
        isActive ? "text-text-primary" : "text-text-muted hover:text-text-secondary transition-colors"
      }
    >
      {children}
    </NavLink>
  );
}
