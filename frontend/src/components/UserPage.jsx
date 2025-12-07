import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function UserPage() {
  const [profile, setProfile] = useState(null);
  const [users, setUsers] = useState([]);
  const [filteredUsers, setFilteredUsers] = useState([]);
  const [usersError, setUsersError] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const [showRegister, setShowRegister] = useState(false);
  const [newUser, setNewUser] = useState({
    name: "",
    is_admin: false,
    permissions: [],
    password: "",
  });

  const token = localStorage.getItem("token");
  const allPermissions = ["search", "upload", "download"];

  // Fetch profile
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoadingProfile(true);
        const res = await fetch(API_ENDPOINTS.PROFILE, {
          headers: { "X-Authorization": token || "" },
        });
        if (!res.ok) throw new Error(`Error fetching profile: ${res.statusText}`);
        const data = await res.json();
        setProfile(data.profile);
      } catch (err) {
        console.error(err);
        setProfile(null);
      } finally {
        setLoadingProfile(false);
      }
    };
    fetchProfile();
  }, [token]);

  // Fetch users (admin only)
  useEffect(() => {
    const fetchUsers = async () => {
      if (!profile?.is_admin) return;
      try {
        setLoadingUsers(true);
        setUsersError(null);
        const res = await fetch(API_ENDPOINTS.USERS, {
          headers: { "X-Authorization": token || "" },
        });
        if (!res.ok) throw new Error(`Error fetching users: ${res.statusText}`);
        const data = await res.json();
        const filtered = data.users.filter((u) => u.name !== profile.name);
        setUsers(filtered);
        setFilteredUsers(filtered);
      } catch (err) {
        console.error(err);
        setUsersError(err.message || "Unable to fetch users");
        setUsers([]);
        setFilteredUsers([]);
      } finally {
        setLoadingUsers(false);
      }
    };

    fetchUsers();
  }, [profile, token]);

  // Delete user
  const handleDelete = async (username) => {
    const confirmed = window.confirm("Are you sure?");
    if (!confirmed) return;
    try {
      const res = await fetch(API_ENDPOINTS.PROFILE, {
        method: "DELETE",
        headers: { "Content-Type": "application/json", "X-Authorization": token || "" },
        body: JSON.stringify({ user: { name: username } }),
      });
      if (!res.ok) throw new Error(`Failed to delete ${username}`);
      alert(`${username} deleted successfully`);
      if (username === profile.name) {
        localStorage.removeItem("token");
        window.location.href = "/";
        return;
      }
      // refetch users
      if (profile?.is_admin) {
        const res = await fetch(API_ENDPOINTS.USERS, {
          headers: { "X-Authorization": token || "" },
        });
        const data = await res.json();
        const filtered = data.users.filter((u) => u.name !== profile.name);
        setUsers(filtered);
        setFilteredUsers(filtered);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Delete failed");
    }
  };

  // Search users
  const handleSearch = (query) => {
    setSearchQuery(query);
    if (!query) setFilteredUsers(users);
    else {
      const lowerQuery = query.toLowerCase();
      setFilteredUsers(users.filter((u) => u.name.toLowerCase().includes(lowerQuery)));
    }
  };

  // Toggle permissions for new user
  const togglePermission = (perm) => {
    if (newUser.is_admin) return;
    setNewUser((prev) => {
      const perms = prev.permissions.includes(perm)
        ? prev.permissions.filter((p) => p !== perm)
        : [...prev.permissions, perm];
      return { ...prev, permissions: perms };
    });
  };

  const handleAdminChange = (checked) => {
    setNewUser((prev) => ({
      ...prev,
      is_admin: checked,
      permissions: checked ? [...allPermissions] : prev.permissions,
    }));
  };

  // Register new user
  const handleRegisterSubmit = async () => {
    if (!newUser.name || !newUser.password) {
      alert("Username and password are required");
      return;
    }
    if (newUser.is_admin) newUser.permissions = [...allPermissions];

    try {
      const res = await fetch(API_ENDPOINTS.REGISTER, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Authorization": token || "" },
        body: JSON.stringify({
          user: {
            name: newUser.name,
            is_admin: newUser.is_admin,
            permissions: newUser.permissions,
          },
          secret: { password: newUser.password },
        }),
      });
      if (!res.ok) throw new Error(`Failed to register user: ${res.statusText}`);
      alert(`User ${newUser.name} registered successfully`);
      setNewUser({ name: "", is_admin: false, permissions: [], password: "" });
      setShowRegister(false);

      // refetch users
      if (profile?.is_admin) {
        const res = await fetch(API_ENDPOINTS.USERS, {
          headers: { "X-Authorization": token || "" },
        });
        const data = await res.json();
        const filtered = data.users.filter((u) => u.name !== profile.name);
        setUsers(filtered);
        setFilteredUsers(filtered);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Register failed");
    }
  };

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>User Profile</h1>
        {loadingProfile ? (
          <LoadingSpinner />
        ) : profile ? (
          <div className="card" style={{ marginBottom: "1.5rem", padding: "1rem" }}>
            <h2>{profile.name}</h2>
            <p>Role: {profile.is_admin ? "Admin" : "User"}</p>
            <p>Permissions: {profile.permissions.join(", ")}</p>
            <p>Requests Made: {profile.request_count}</p>
            <button
              onClick={() => handleDelete(profile.name)}
              style={{
                padding: "0.25rem 0.5rem",
                backgroundColor: "#ef4444",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.75rem",
                marginTop: "0.5rem",
              }}
            >
              Delete Profile
            </button>
          </div>
        ) : (
          <ErrorBanner message="Unable to fetch profile" />
        )}

        {profile?.is_admin && (
          <>
            <h1>All Users</h1>

            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem", gap: "1rem" }}>
              <button
                onClick={() => setShowRegister(true)}
                style={{
                  padding: "0.5rem 1rem",
                  backgroundColor: "#3b82f6",
                  color: "white",
                  border: "none",
                  borderRadius: "5px",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                }}
              >
                Register User
              </button>

              <input
                type="text"
                placeholder="Search users..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                style={{
                  padding: "0.5rem",
                  borderRadius: "5px",
                  border: "1px solid #ccc",
                  flexGrow: 1,
                }}
              />
            </div>

            <ErrorBanner message={usersError} />
            {loadingUsers ? (
              <LoadingSpinner />
            ) : filteredUsers.length === 0 ? (
              <p>No users have been registered</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                {filteredUsers.map((user) => (
                  <div
                    key={user.name}
                    className="card"
                    style={{
                      padding: "0.7rem 1rem",
                      borderRadius: "6px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.3rem",
                    }}
                  >
                    <div>
                      <p style={{ margin: 0, fontWeight: "bold", fontSize: "1rem" }}>{user.name}</p>
                      <p style={{ margin: "0.1rem 0", fontSize: "0.85rem", color: "#555" }}>
                        {user.is_admin ? "Admin" : "User"}
                      </p>
                      <p style={{ margin: 0, fontSize: "0.8rem", color: "#777" }}>
                        Permissions: {user.permissions.join(", ")}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDelete(user.name)}
                      style={{
                        padding: "0.15rem 0.3rem",
                        backgroundColor: "#ef4444",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                        fontSize: "0.65rem",
                        alignSelf: "flex-start",
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}

            {showRegister && (
              <div
                style={{
                  position: "fixed",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  backgroundColor: "rgba(0,0,0,0.4)",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  zIndex: 999,
                }}
              >
                <div
                  className="card"
                  style={{
                    padding: "1.5rem",
                    width: "380px",
                    backgroundColor: "#f0f4f8",
                    borderRadius: "8px",
                    boxShadow: "0 6px 16px rgba(0,0,0,0.2)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.8rem",
                    color: "#000",
                  }}
                >
                  <h2 style={{ marginBottom: "0.5rem" }}>Register New User</h2>

                  <label style={{ color: "#000" }}>
                    Username:
                    <input
                      type="text"
                      value={newUser.name}
                      onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                      style={{ width: "100%", padding: "0.4rem", marginTop: "0.2rem", borderRadius: "4px", border: "1px solid #ccc", color: "#fff", backgroundColor: "#1f2937" }}
                    />
                  </label>

                  <label style={{ display: "flex", alignItems: "center", gap: "0.3rem", color: "#000" }}>
                    Admin
                    <input
                      type="checkbox"
                      checked={newUser.is_admin}
                      onChange={(e) => handleAdminChange(e.target.checked)}
                    />
                  </label>

                  <label style={{ color: "#000" }}>
                    Permissions:
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.2rem" }}>
                      {allPermissions.map((perm) => (
                        <label key={perm} style={{ display: "flex", alignItems: "center", gap: "0.2rem", color: "#000" }}>
                          <input
                            type="checkbox"
                            checked={newUser.permissions.includes(perm)}
                            onChange={() => togglePermission(perm)}
                            disabled={newUser.is_admin}
                          />
                          {perm.charAt(0).toUpperCase() + perm.slice(1)}
                        </label>
                      ))}
                    </div>
                  </label>

                  <label style={{ color: "#000" }}>
                    Password:
                    <input
                      type="password"
                      value={newUser.password}
                      onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                      style={{ width: "100%", padding: "0.4rem", marginTop: "0.2rem", borderRadius: "4px", border: "1px solid #ccc", color: "#fff", backgroundColor: "#1f2937" }}
                    />
                  </label>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                    <button
                      onClick={handleRegisterSubmit}
                      style={{
                        padding: "0.35rem 0.7rem",
                        backgroundColor: "#3b82f6",
                        color: "white",
                        border: "none",
                        borderRadius: "5px",
                        cursor: "pointer",
                        fontSize: "0.85rem",
                      }}
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setShowRegister(false)}
                      style={{
                        padding: "0.35rem 0.7rem",
                        backgroundColor: "#ccc",
                        border: "none",
                        borderRadius: "5px",
                        cursor: "pointer",
                        fontSize: "0.85rem",
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
