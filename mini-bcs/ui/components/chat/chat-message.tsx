"use client";

import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

export interface ChatMessageData {
  id: string;
  author: "user" | "agent";
  content: string;
  type?: "message" | "error";
}

const markdownComponents: Components = {
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-primary underline underline-offset-2 hover:text-primary/80 break-all"
    >
      {children}
      <ExternalLink className="inline h-3 w-3 shrink-0" />
    </a>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-lg border">
      <table className="min-w-full text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-muted/60">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-t px-3 py-1.5">{children}</td>
  ),
  ul: ({ children }) => (
    <ul className="my-1 ml-4 list-disc space-y-0.5 marker:text-muted-foreground/50">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1 ml-4 list-decimal space-y-0.5 marker:text-muted-foreground/50">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  code: ({ className, children }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <pre className="my-2 overflow-x-auto rounded-lg bg-muted/60 p-3 text-xs">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="rounded bg-muted/60 px-1 py-0.5 text-xs">
        {children}
      </code>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-primary/30 pl-3 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  h1: ({ children }) => (
    <h1 className="mb-1 mt-3 text-base font-bold first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1 mt-3 text-sm font-bold first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-0.5 mt-2 text-sm font-semibold first:mt-0">
      {children}
    </h3>
  ),
  hr: () => <hr className="my-3 border-border" />,
};

export function ChatMessage({ message }: { message: ChatMessageData }) {
  const isUser = message.author === "user";
  const isError = message.type === "error";

  return (
    <div
      className={cn(
        "flex gap-3 px-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {!isUser && (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="bg-primary text-primary-foreground text-xs">
            BCS
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : isError
              ? "bg-destructive/10 text-destructive border border-destructive/20"
              : "bg-muted text-foreground"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {message.content}
            </Markdown>
          </div>
        )}
      </div>
    </div>
  );
}
