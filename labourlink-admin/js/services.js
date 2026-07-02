const API = "http://localhost:5000/api/services";

let modal;

window.onload = () => {

    modal = new bootstrap.Modal(document.getElementById("serviceModal"));

    loadServices();

};

// =======================
// Load Services
// =======================

async function loadServices() {

    try {

        const res = await fetch(API);

        const services = await res.json();

        const table = document.getElementById("serviceTable");

        table.innerHTML = "";

        services.forEach(service => {

            table.innerHTML += `

            <tr>

                <td style="font-size:28px">
                    ${service.icon}
                </td>

                <td>
                    ${service.name}
                </td>

                <td>
                    ${service.description}
                </td>

                <td>

                    ${
                        service.status
                        ?
                        '<span class="badge bg-success">Active</span>'
                        :
                        '<span class="badge bg-danger">Inactive</span>'
                    }

                </td>

                <td>

                    <button
                        class="btn btn-primary btn-sm"
                        onclick="editService('${service._id}')">

                        Edit

                    </button>

                    <button
                        class="btn btn-danger btn-sm"
                        onclick="deleteService('${service._id}')">

                        Delete

                    </button>

                </td>

            </tr>

            `;

        });

    }

    catch(err){

        console.log(err);

        alert("Unable to load services.");

    }

}

// =======================
// Open Modal
// =======================

function openModal(){

    document.getElementById("serviceId").value="";

    document.getElementById("serviceName").value="";

    document.getElementById("serviceDesc").value="";

    document.getElementById("serviceIcon").value="";

    document.getElementById("serviceStatus").value="true";

    modal.show();

}

// =======================
// Save
// =======================

async function saveService(){

    const id=document.getElementById("serviceId").value;

    const data={

        name:document.getElementById("serviceName").value,

        description:document.getElementById("serviceDesc").value,

        icon:document.getElementById("serviceIcon").value,

        status:document.getElementById("serviceStatus").value==="true"

    };

    try{

        if(id){

            await fetch(API+"/"+id,{

                method:"PUT",

                headers:{

                    "Content-Type":"application/json"

                },

                body:JSON.stringify(data)

            });

        }

        else{

            await fetch(API,{

                method:"POST",

                headers:{

                    "Content-Type":"application/json"

                },

                body:JSON.stringify(data)

            });

        }

        modal.hide();

        loadServices();

    }

    catch(err){

        console.log(err);

        alert("Save failed");

    }

}

// =======================
// Edit
// =======================

async function editService(id){

    const res=await fetch(API);

    const services=await res.json();

    const service=services.find(s=>s._id===id);

    if(!service) return;

    document.getElementById("serviceId").value=service._id;

    document.getElementById("serviceName").value=service.name;

    document.getElementById("serviceDesc").value=service.description;

    document.getElementById("serviceIcon").value=service.icon;

    document.getElementById("serviceStatus").value=service.status;

    modal.show();

}

// =======================
// Delete
// =======================

async function deleteService(id){

    if(!confirm("Delete this service?")) return;

    await fetch(API+"/"+id,{

        method:"DELETE"

    });

    loadServices();

}