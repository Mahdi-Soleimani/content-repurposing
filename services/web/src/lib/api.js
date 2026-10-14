const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function initUpload(projectId, file) {
  const res = await fetch(`${API_URL}/api/uploads/init`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      file_size: file.size,
    }),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to initialize upload: ${res.statusText}`);
  }
  return res.json();
}

export function uploadToS3(uploadUrl, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        if (onProgress) onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`S3 upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during S3 upload"));
    };

    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.send(file);
  });
}

export async function completeUpload(uploadId) {
  const res = await fetch(`${API_URL}/api/uploads/${uploadId}/complete`, {
    method: "POST",
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to complete upload: ${res.statusText}`);
  }
  return res.json();
}


export async function submitText(projectId, text) {
  const res = await fetch(`${API_URL}/api/content/text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      content: text,
    }),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to submit text: ${res.statusText}`);
  }
  return res.json();
}

export async function submitUrl(projectId, url) {
  const res = await fetch(`${API_URL}/api/content/url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      url: url,
    }),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to submit URL: ${res.statusText}`);
  }
  return res.json();
}

// ──── Projects API ────

export async function getProjects() {
  const res = await fetch(`${API_URL}/api/projects`);
  if (!res.ok) throw new Error("Failed to load projects");
  return res.json();
}

export async function createProject(name = "My Workspace", description = "") {
  const res = await fetch(`${API_URL}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error("Failed to create project");
  return res.json();
}

export async function deleteProject(projectId) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to delete project");
  }
  return res.json();
}

export async function renameProject(projectId, name) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to rename project");
  }
  return res.json();
}

export async function getProjectWorkspace(projectId) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/workspace`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error("Failed to load workspace");
  }
  return res.json();
}

export async function updateProjectSettings(projectId, settings) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error("Failed to update project settings");
  return res.json();
}

// ──── Generation API ────

export async function updateDraft(projectId, requestedOutputs) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/generation/draft`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requested_outputs: requestedOutputs }),
  });
  if (!res.ok) throw new Error("Failed to update draft");
  return res.json();
}

export async function generateContent(projectId, transcriptId, requestedOutputs) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/generation/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript_id: transcriptId,
      requested_outputs: requestedOutputs
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to trigger generation");
  }
  return res.json();
}

export async function discardTranscript(projectId, transcriptId) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/generation/${transcriptId}/discard`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to discard transcript");
  }
  return res.json();
}

export async function getJobOutputs(projectId, jobId, limit = 50, offset = 0) {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/jobs/${jobId}/outputs?limit=${limit}&offset=${offset}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to load job outputs");
  }
  return res.json();
}

// ──── Settings API ────

export async function uploadYoutubeCookies(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/settings/youtube/cookies`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to upload YouTube cookies");
  }
  return res.json();
}

export async function testYoutubeCookies() {
  const res = await fetch(`${API_URL}/api/settings/youtube/test`, {
    method: "POST",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to test YouTube cookies");
  }
  return res.json();
}
