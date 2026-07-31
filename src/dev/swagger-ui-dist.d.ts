/**
 * Minimal typings for the one Swagger UI entry point the local docs page uses.
 * swagger-ui-dist ships no declarations of its own, and `@types/swagger-ui-dist`
 * only describes the CommonJS root module — not the `swagger-ui-bundle.js` deep
 * import that Vite can actually pre-bundle. Only the options set in
 * `apiDocs.ts` are declared; add more as needed.
 */
declare module 'swagger-ui-dist/swagger-ui-bundle.js' {
  interface SwaggerUIRequest {
    url: string;
    [key: string]: unknown;
  }

  interface SwaggerUIOptions {
    domNode: Element;
    url?: string;
    deepLinking?: boolean;
    displayRequestDuration?: boolean;
    defaultModelsExpandDepth?: number;
    tryItOutEnabled?: boolean;
    requestInterceptor?: (request: SwaggerUIRequest) => SwaggerUIRequest;
  }

  const SwaggerUIBundle: (options: SwaggerUIOptions) => unknown;
  export default SwaggerUIBundle;
}
