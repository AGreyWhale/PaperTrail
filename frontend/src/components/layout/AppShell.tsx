import { Link, Outlet } from "react-router-dom";
import { Show, SignInButton, SignOutButton, UserButton, useAuth } from "@clerk/react";
import { Button } from "../ui/Button";

//Nav bar + routed page below it. Kept minimal so the content carries the page
export function AppShell() {
  const { isLoaded } = useAuth();

  if (!isLoaded) return null;

  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border bg-surface">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="font-serif text-xl text-text-primary">
            PaperTrail
          </Link>

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

      <main>
        <Outlet />
      </main>
    </div>
  );
}
