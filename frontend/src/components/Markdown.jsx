import React from 'react';
import ReactMarkdown from 'react-markdown';

// Renders AI-written markdown (summaries, chat answers) with the app's own type styles.
// Raw HTML in the text is ignored, so model output can't inject markup.
const components = {
  h1: (props) => <h3 className="text-base sm:text-lg font-extrabold text-slate-900 mt-5 mb-2 first:mt-0" {...props} />,
  h2: (props) => <h3 className="text-base sm:text-lg font-extrabold text-slate-900 mt-5 mb-2 first:mt-0" {...props} />,
  h3: (props) => <h4 className="text-sm sm:text-base font-bold text-slate-900 mt-4 mb-2 first:mt-0" {...props} />,
  h4: (props) => <h5 className="font-bold text-slate-900 mt-3 mb-1 first:mt-0" {...props} />,
  p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
  ul: (props) => <ul className="my-2 pl-5 list-disc space-y-1.5 marker:text-slate-400" {...props} />,
  ol: (props) => <ol className="my-2 pl-5 list-decimal space-y-1.5 marker:text-slate-400" {...props} />,
  strong: (props) => <strong className="font-bold text-slate-900" {...props} />,
  blockquote: (props) => (
    <blockquote className="my-3 pl-3 border-l-2 border-amber-300 text-slate-600 italic" {...props} />
  ),
  code: (props) => <code className="px-1 py-0.5 rounded bg-slate-100 font-mono text-[0.9em]" {...props} />,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2 text-amber-700">
      {children}
    </a>
  ),
};

export default function Markdown({ children, className = '' }) {
  return (
    <div className={className}>
      <ReactMarkdown components={components} skipHtml>
        {children || ''}
      </ReactMarkdown>
    </div>
  );
}
