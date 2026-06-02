# 04 — API 设计

> Base URL: `http://localhost:8000/api/v1`  
> 认证方式: `Authorization: Bearer <access_token>`  
> 响应格式: JSON，`{ "code": 0, "data": ..., "message": "ok" }`

---

## 1. 认证 Auth

### POST /auth/register

注册新用户。

**Request**

```json
{
  "email": "user@example.com",
  "username": "zhangsan",
  "password": "SecurePass123"
}
```

**Response 201**

```json
{
  "code": 0,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "username": "zhangsan"
  }
}
```

---

### POST /auth/login

**Request**

```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response 200**

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 7200
  }
}
```

---

### GET /auth/me

获取当前用户信息。需认证。

---

## 2. 知识库 Knowledge Bases

### GET /knowledge-bases

列表（分页）。

**Query**: `page=1&page_size=20`

**Response**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "操作系统笔记",
        "description": "期末复习资料",
        "document_count": 5,
        "created_at": "2026-06-01T10:00:00Z"
      }
    ],
    "total": 1
  }
}
```

---

### POST /knowledge-bases

创建知识库。

**Request**

```json
{
  "name": "机器学习",
  "description": "课程 PDF 与笔记"
}
```

---

### GET /knowledge-bases/{kb_id}

详情。

---

### PUT /knowledge-bases/{kb_id}

更新名称/描述。

---

### DELETE /knowledge-bases/{kb_id}

删除知识库及下属文档、向量、对话（级联）。

---

## 3. 文档 Documents

### GET /knowledge-bases/{kb_id}/documents

文档列表。

**Response item**

```json
{
  "id": "uuid",
  "title": "OS-chapter3.pdf",
  "file_type": "pdf",
  "file_size": 1048576,
  "status": "ready",
  "chunk_count": 42,
  "error_message": null,
  "created_at": "2026-06-01T11:00:00Z"
}
```

`status`: `pending` | `processing` | `ready` | `failed`

---

### POST /knowledge-bases/{kb_id}/documents

上传文档（multipart/form-data）。

**Form fields**

| 字段 | 类型 | 说明 |
|------|------|------|
| file | File | PDF / .md / .txt |
| title | string | 可选，默认文件名 |

**Response 202**（异步处理）

```json
{
  "code": 0,
  "data": {
    "document_id": "uuid",
    "status": "pending",
    "message": "文档已上传，正在解析索引"
  }
}
```

---

### GET /documents/{doc_id}

查询文档详情与处理状态（前端轮询用）。

---

### DELETE /documents/{doc_id}

删除文档及关联 chunks。

---

## 4. 对话 Chat

### GET /knowledge-bases/{kb_id}/conversations

会话列表。

---

### POST /knowledge-bases/{kb_id}/conversations

创建新会话。

**Request**

```json
{
  "title": "可选，默认自动生成"
}
```

---

### GET /conversations/{conv_id}/messages

获取会话消息历史。

**Response**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "role": "user",
        "content": "什么是虚拟内存？",
        "created_at": "..."
      },
      {
        "id": "uuid",
        "role": "assistant",
        "content": "虚拟内存是...[1]",
        "citations": [
          {
            "index": 1,
            "chunk_id": "uuid",
            "document_title": "OS-chapter3.pdf",
            "page_number": 12,
            "excerpt": "虚拟内存将物理内存和磁盘存储结合起来...",
            "score": 0.89
          }
        ],
        "created_at": "..."
      }
    ]
  }
}
```

---

### POST /conversations/{conv_id}/chat

发送问题并获取回答（非流式）。

**Request**

```json
{
  "question": "页表的作用是什么？",
  "top_k": 6
}
```

**Response 200**

```json
{
  "code": 0,
  "data": {
    "message_id": "uuid",
    "answer": "页表用于映射虚拟地址到物理地址...[1][2]",
    "citations": [ ... ],
    "latency_ms": 2340
  }
}
```

---

### POST /conversations/{conv_id}/chat/stream

流式问答（SSE）。

**Response**: `Content-Type: text/event-stream`

```
event: token
data: {"content": "页表"}

event: token
data: {"content": "用于"}

event: done
data: {"message_id": "uuid", "citations": [...]}
```

---

## 5. 健康检查

### GET /health

```json
{ "status": "ok", "db": "connected", "redis": "connected" }
```

---

## 6. 错误码

| HTTP | code | 说明 |
|------|------|------|
| 400 | 40001 | 参数校验失败 |
| 401 | 40101 | 未登录或 Token 无效 |
| 403 | 40301 | 无权访问该资源 |
| 404 | 40401 | 资源不存在 |
| 413 | 41301 | 文件过大 |
| 429 | 42901 | 请求过于频繁 |
| 500 | 50001 | 服务器内部错误 |

**错误响应示例**

```json
{
  "code": 40101,
  "message": "Invalid or expired token",
  "data": null
}
```

---

## 7. 前端调用流程

### 上传并等待就绪

```
1. POST /knowledge-bases/{kb_id}/documents  (upload)
2. loop: GET /documents/{doc_id}  every 2s
   until status == ready || failed
3. 展示 ready → 可开始对话
```

### 对话

```
1. POST /knowledge-bases/{kb_id}/conversations  (若无会话)
2. POST /conversations/{conv_id}/chat/stream
3. 渲染 SSE token + 最终 citations 侧边栏
```

---

## 8. OpenAPI

FastAPI 自动生成文档：`http://localhost:8000/docs`

实现时每个 router 写好 `summary`、`response_model`，便于前后端联调。
