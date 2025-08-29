import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [functionPrompt, setFunctionPrompt] = useState('');
  const [functionResult, setFunctionResult] = useState('');
  const [isFunctionCalling, setIsFunctionCalling] = useState(false);
  const [capabilities, setCapabilities] = useState({});

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const result = await axios.post('http://localhost:8000/chat', {
        prompt: prompt
      });
      setResponse(result.data.response);
    } catch (err) {
      alert('Error: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsLoading(false);
    }
  };

  const executeFunctionCalling = async () => {
    setIsFunctionCalling(true);
    try {
      const result = await axios.post('http://localhost:8000/function-calling/execute', {
        prompt: functionPrompt
      });
      setFunctionResult(result.data.result);
    } catch (err) {
      alert('Error: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsFunctionCalling(false);
    }
  };

  const runDemo = async () => {
    setIsFunctionCalling(true);
    try {
      const result = await axios.post('http://localhost:8000/function-calling/demo');
      setFunctionPrompt("What's the weather in Tokyo and New York? Also show me AAPL stock price.");
      setFunctionResult(result.data.result);
    } catch (err) {
      alert('Error: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsFunctionCalling(false);
    }
  };

  useEffect(() => {
    axios.get('http://localhost:8000/function-calling/capabilities')
      .then(result => setCapabilities(result.data))
      .catch(err => console.error('Error loading capabilities:', err));
  }, []);

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ textAlign: 'center', marginBottom: '2rem' }}>AI Chat System</h1>
      
      {/* Simple Chat */}
      <div style={{ marginBottom: '2rem', padding: '1.5rem', border: '2px solid #0070f3', borderRadius: '8px' }}>
        <h2>Simple Chat</h2>
        <form onSubmit={handleSubmit}>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows="3"
            style={{ width: '100%', padding: '0.75rem', marginBottom: '1rem', border: '2px solid #0070f3', borderRadius: '6px' }}
            placeholder="Ask something..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Processing...' : 'Send'}
          </button>
        </form>
        {response && (
          <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#f5f5f5', borderRadius: '6px' }}>
            {response}
          </div>
        )}
      </div>

      {/* Function Calling */}
      <div style={{ padding: '1.5rem', border: '2px solid #2196f3', borderRadius: '8px', backgroundColor: '#e3f2fd' }}>
        <h2>Function Calling</h2>
        <div style={{ marginBottom: '1rem' }}>
          <strong>Model:</strong> {capabilities.current_deployment || 'Loading...'}
        </div>
        <textarea
          value={functionPrompt}
          onChange={(e) => setFunctionPrompt(e.target.value)}
          rows="3"
          style={{ width: '100%', padding: '0.75rem', marginBottom: '1rem', border: '2px solid #2196f3', borderRadius: '6px' }}
          placeholder="Ask about weather, stocks, or sentiment..."
          disabled={isFunctionCalling}
        />
        <div>
          <button onClick={executeFunctionCalling} disabled={isFunctionCalling} style={{ marginRight: '1rem' }}>
            {isFunctionCalling ? 'Calling...' : 'Execute'}
          </button>
          <button onClick={runDemo} disabled={isFunctionCalling}>
            Run Demo
          </button>
        </div>
        {functionResult && (
          <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'white', borderRadius: '6px' }}>
            {functionResult}
          </div>
        )}
      </div>
    </div>
  );
}