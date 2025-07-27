import { fetch } from "@tauri-apps/plugin-http";
import { openUrl } from "@tauri-apps/plugin-opener";

const API_BASE_URL = "http://localhost:8000";

export interface User {
  id: number;
  github_username: string;
  github_email?: string;
  avatar_url?: string;
}

export interface SessionResponse {
  user: User;
  session_expires_at: string;
}

export class AuthService {
  async initiateGitHubOAuth(): Promise<void> {
    console.log('[AuthService] Initiating GitHub OAuth flow');
    try {
      console.log(`[AuthService] Making request to: ${API_BASE_URL}/api/auth/github`);
      const response = await fetch(`${API_BASE_URL}/api/auth/github`);

      console.log(`[AuthService] GitHub OAuth response status: ${response.status}`);
      console.log(`[AuthService] GitHub OAuth response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const error = `GitHub OAuth request failed: ${response.status}`;
        console.error(`[AuthService] ${error}`);
        throw new Error(error);
      }

      // The backend returns a redirect response, we need to get the redirect URL
      const redirectUrl = response.url;
      console.log(`[AuthService] Got redirect URL: ${redirectUrl}`);

      // Open the GitHub OAuth URL in the default browser
      console.log('[AuthService] Opening GitHub OAuth URL in browser');
      await openUrl(redirectUrl);
      console.log('[AuthService] Successfully opened GitHub OAuth URL');
    } catch (error) {
      console.error("[AuthService] GitHub OAuth initiation failed:", error);
      throw error;
    }
  }

  async createSession(sessionCode: string): Promise<SessionResponse> {
    console.log(`[AuthService] Creating session with code: ${sessionCode.substring(0, 8)}...`);
    try {
      const requestBody = { session_code: sessionCode };
      console.log(`[AuthService] Making POST request to: ${API_BASE_URL}/api/auth/session`);
      console.log(`[AuthService] Request body:`, requestBody);
      
      const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        credentials: 'include', // Include cookies and allow setting cookies
      });

      console.log(`[AuthService] Session creation response status: ${response.status}`);
      console.log(`[AuthService] Session creation response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[AuthService] Session creation failed with status ${response.status}: ${errorText}`);
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const sessionData: SessionResponse = await response.json();
      console.log(`[AuthService] Successfully created session for user: ${sessionData.user.github_username}`);
      console.log(`[AuthService] Session expires at: ${sessionData.session_expires_at}`);
      
      // ✅ Session established via HTTP-only cookie - no localStorage needed
      console.log(`[AuthService] Session established via secure HTTP-only cookie for user: ${sessionData.user.github_username}`);
      return sessionData;
    } catch (error) {
      console.error("[AuthService] Session creation failed:", error);
      throw error;
    }
  }

  async getCurrentUser(): Promise<User | null> {
    console.log('[AuthService] Getting current user');
    try {
      console.log(`[AuthService] Making GET request to: ${API_BASE_URL}/api/auth/me`);
      
      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        method: 'GET',
        credentials: 'include', // Include cookies for session authentication
      });

      console.log(`[AuthService] Current user response status: ${response.status}`);
      console.log(`[AuthService] Current user response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        console.log(`[AuthService] Session validation failed with status ${response.status}, user not authenticated`);
        return null;
      }

      const user: User = await response.json();
      console.log(`[AuthService] Successfully validated session for user: ${user.github_username}`);
      console.log(`[AuthService] User data:`, {
        id: user.id,
        github_username: user.github_username,
        github_email: user.github_email,
        has_avatar: !!user.avatar_url
      });
      
      return user;
    } catch (error) {
      console.error("[AuthService] Get current user failed:", error);
      return null;
    }
  }

  async logout(): Promise<void> {
    console.log('[AuthService] Logging out user');
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include', // Include cookies for session authentication
      });

      if (response.ok) {
        console.log('[AuthService] Successfully logged out user');
      } else {
        console.warn(`[AuthService] Logout request failed with status ${response.status}`);
      }
    } catch (error) {
      console.error("[AuthService] Logout failed:", error);
      // Don't throw error for logout - user should still be considered logged out
    }
  }

  async isAuthenticated(): Promise<boolean> {
    console.log('[AuthService] Checking authentication status');
    try {
      const user = await this.getCurrentUser();
      const isAuth = user !== null;
      console.log(`[AuthService] Is authenticated: ${isAuth}`);
      return isAuth;
    } catch (error) {
      console.error("[AuthService] Authentication check failed:", error);
      return false;
    }
  }
}

export const authService = new AuthService();
