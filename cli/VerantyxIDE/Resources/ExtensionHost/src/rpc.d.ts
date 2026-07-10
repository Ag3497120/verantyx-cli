export declare class RPCClient {
    private requestIDCounter;
    private pendingRequests;
    private notificationListeners;
    constructor();
    private handleMessage;
    private handleRequestFromSwift;
    onNotification(method: string, listener: (params: any) => void): void;
    sendNotification(method: string, params?: any): void;
    sendRequest(method: string, params?: any): Promise<any>;
    private sendResponse;
}
//# sourceMappingURL=rpc.d.ts.map