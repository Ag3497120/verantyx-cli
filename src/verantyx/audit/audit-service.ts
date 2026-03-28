/**
 * GeminiAuditService — Top-level service combining all audit components
 */

import { GeminiBridge } from "./gemini-bridge.js";
import { MemoryAuditor, AuditResult, AuditSummary } from "./memory-auditor.js";
import { OperationAuditor, OperationRequest, OperationDecision } from "./operation-auditor.js";
import { TodoManager, TodoAuditResult } from "./todo-manager.js";

export interface FullAuditReport {
  memory: AuditSummary;
  todo: TodoAuditResult;
  timestamp: string;
}

export class GeminiAuditService {
  private bridge: GeminiBridge;
  private memoryAuditor: MemoryAuditor;
  private operationAuditor: OperationAuditor;
  private todoManager: TodoManager;
  private initialized = false;

  constructor(memoryRoot: string) {
    this.bridge = new GeminiBridge();
    this.memoryAuditor = new MemoryAuditor(this.bridge, memoryRoot);
    this.operationAuditor = new OperationAuditor(this.bridge);
    this.todoManager = new TodoManager(this.bridge, memoryRoot);
  }

  async initialize(): Promise<void> {
    if (this.initialized) {return;}
    await this.bridge.initialize();
    this.initialized = true;
  }

  async auditMemory(zone: string, name: string): Promise<AuditResult> {
    await this.ensureInit();
    return this.memoryAuditor.auditMemory(zone, name);
  }

  async validateOperation(request: OperationRequest): Promise<OperationDecision> {
    await this.ensureInit();
    return this.operationAuditor.validateOperation(request);
  }

  async auditTodos(): Promise<TodoAuditResult> {
    await this.ensureInit();
    return this.todoManager.auditTodos();
  }

  async runFullAudit(): Promise<FullAuditReport> {
    await this.ensureInit();
    const memory = await this.memoryAuditor.runPeriodicAudit();
    const todo = await this.todoManager.auditTodos();
    return { memory, todo, timestamp: new Date().toISOString() };
  }

  shutdown(): void {
    this.bridge.cleanup();
    this.initialized = false;
  }

  // expose for direct use
  getTodoManager(): TodoManager { return this.todoManager; }
  getMemoryAuditor(): MemoryAuditor { return this.memoryAuditor; }
  getBridge(): GeminiBridge { return this.bridge; }

  private async ensureInit(): Promise<void> {
    if (!this.initialized) {await this.initialize();}
  }
}

// Re-export all types
export type { AuditResult, AuditSummary } from "./memory-auditor.js";
export type { OperationRequest, OperationDecision } from "./operation-auditor.js";
export type { TodoAuditResult, TodoItem } from "./todo-manager.js";
export type { AskResult } from "./safari-controller.js";
