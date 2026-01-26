import ChatInterface from '@/components/ChatInterface';

export default function ChatPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-12 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            GDG Knowledge Base
          </h1>
          <p className="text-gray-600">
            Get instant answers about our Google Developer Group
          </p>
        </div>
        
        <ChatInterface />
        
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Powered by Google Gemini AI</p>
        </div>
      </div>
    </div>
  );
}
```

### Step 2.6: Create Admin Upload Page

Create `app/admin-upload/page.tsx`:

```bash
mkdir app/admin-upload
```

Create file `app/admin-upload/page.tsx`:

```typescript
'use client';

import { useState } from 'react';

export default function AdminUploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setMessage('');
      setError('');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setUploading(true);
    setMessage('');
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/upload`, {
        method: 'POST',
        headers: {
          'x-admin-token': process.env.NEXT_PUBLIC_ADMIN_TOKEN || '',
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setMessage(`✅ Success! ${data.filename} uploaded with ${data.chunks_added} chunks.`);
      setFile(null);
      
      // Reset file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
    } catch (err: any) {
      setError(`❌ Error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-red-50 to-white py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              🔒 Admin Upload
            </h1>
            <p className="text-gray-600">
              Upload PDF documents to the GDG knowledge base
            </p>
            <p className="text-sm text-red-600 mt-2">
              ⚠️ This page is for administrators only
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select PDF File
              </label>
              <input
                id="file-input"
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-50 file:text-blue-700
                  hover:file:bg-blue-100
                  cursor-pointer"
                disabled={uploading}
              />
            </div>

            {file && (
              <div className="bg-gray-50 p-3 rounded-lg">
                <p className="text-sm text-gray-700">
                  <span className="font-semibold">Selected:</span> {file.name}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Size: {(file.size / 1024).toFixed(2)} KB
                </p>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg
                hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                transition-colors font-semibold"
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </button>

            {message && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-green-800">{message}</p>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-800">{error}</p>
              </div>
            )}
          </div>

          <div className="mt-8 pt-6 border-t">
            <h3 className="font-semibold text-gray-900 mb-2">Instructions:</h3>
            <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
              <li>Only PDF files are supported</li>
              <li>Documents are automatically chunked and embedded</li>
              <li>Uploaded documents are immediately available for chat</li>
              <li>Keep this page URL private (dev/admin only)</li>
            </ul>
          </div>
        </div>

        <div className="mt-4 text-center">
          <a
            href="/chat"
            className="text-blue-600 hover:text-blue-800 underline"
          >
            Go to Chat Interface
          </a>
        </div>
      </div>
    </div>
  );
}