import { ImageResponse } from 'next/og';

export const runtime = 'edge';
export const alt = 'HC AI — Healthcare RAG Demo';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OGImage() {
  const stats = [
    { label: 'Patients', value: '91K' },
    { label: 'Vectors', value: '7.7M' },
    { label: 'Medical Tools', value: '20+' },
    { label: 'AWS Monthly', value: '~$120' },
  ];

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #0a0a0f 0%, #111827 50%, #0a0a0f 100%)',
          fontFamily: 'system-ui, sans-serif',
          padding: '60px',
        }}
      >
        {/* Accent glow */}
        <div
          style={{
            position: 'absolute',
            top: '-100px',
            left: '-100px',
            width: '400px',
            height: '400px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(20,184,166,0.15) 0%, transparent 70%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: '-100px',
            right: '-100px',
            width: '500px',
            height: '500px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 70%)',
          }}
        />

        {/* Title */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            marginBottom: '16px',
          }}
        >
          <div
            style={{
              fontSize: '64px',
              fontWeight: 800,
              color: '#f9fafb',
              letterSpacing: '-0.02em',
            }}
          >
            HC AI
          </div>
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontSize: '28px',
            fontWeight: 500,
            color: '#14b8a6',
            marginBottom: '12px',
          }}
        >
          Healthcare RAG Demo
        </div>

        {/* Builder */}
        <div
          style={{
            fontSize: '20px',
            color: '#9ca3af',
            marginBottom: '48px',
          }}
        >
          Built by Raphael San Andres
        </div>

        {/* Stats */}
        <div
          style={{
            display: 'flex',
            gap: '32px',
          }}
        >
          {stats.map((stat) => (
            <div
              key={stat.label}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '20px 32px',
                borderRadius: '12px',
                border: '1px solid rgba(255,255,255,0.1)',
                background: 'rgba(255,255,255,0.03)',
              }}
            >
              <div
                style={{
                  fontSize: '28px',
                  fontWeight: 700,
                  color: '#f9fafb',
                  marginBottom: '4px',
                }}
              >
                {stat.value}
              </div>
              <div
                style={{
                  fontSize: '14px',
                  color: '#6b7280',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Tech stack */}
        <div
          style={{
            display: 'flex',
            gap: '12px',
            marginTop: '36px',
          }}
        >
          {['Python', 'LangGraph', 'pgvector', 'AWS ECS', 'Claude 3.5', 'Next.js'].map(
            (tech) => (
              <div
                key={tech}
                style={{
                  fontSize: '14px',
                  color: '#9ca3af',
                  padding: '6px 14px',
                  borderRadius: '20px',
                  background: 'rgba(20,184,166,0.08)',
                  border: '1px solid rgba(20,184,166,0.15)',
                }}
              >
                {tech}
              </div>
            )
          )}
        </div>
      </div>
    ),
    { ...size }
  );
}
