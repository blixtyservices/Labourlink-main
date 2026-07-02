const API = "http://172.20.10.3:8000/api";

async function loadUsers() {
    try {
        const response = await fetch(`${API}/users`);

        if (!response.ok) {
            throw new Error("Failed to load users");
        }

        const users = await response.json();

        const table = document.getElementById("userTable");
        table.innerHTML = "";

        users.forEach(user => {

            table.innerHTML += `
                <tr>
                    <td>${user.name}</td>
                    <td>${user.email}</td>
                    <td>${user.phone || "-"}</td>
                    <td>${user.city || "-"}</td>
                    <td>
                        <span class="badge bg-success">
                            Active
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-danger">
                            Block
                        </button>
                    </td>
                </tr>
            `;

        });

    } catch (error) {

        console.error(error);

        document.getElementById("userTable").innerHTML = `
            <tr>
                <td colspan="6" style="text-align:center;color:red;">
                    Failed to load users.
                </td>
            </tr>
        `;

    }
}

loadUsers();