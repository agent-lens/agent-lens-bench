@file:Suppress("PROVIDED_RUNTIME_TOO_LOW")
package com.anonymous.benchmark.common.runner.agent.engine

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.schema.ToolCall
import com.anonymous.benchmark.common.schema.ToolResponse
import com.anonymous.benchmark.common.schema.MessageKind
import kotlinx.coroutines.future.await
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.Json
import kotlinx.serialization.modules.SerializersModule
import kotlinx.serialization.modules.contextual
import kotlinx.serialization.serializer
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.util.*


object UUIDSerializer : KSerializer<UUID> {
    override val descriptor: SerialDescriptor = PrimitiveSerialDescriptor("UUID", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: UUID) {
        encoder.encodeString(value.toString())
    }

    override fun deserialize(decoder: Decoder): UUID {
        return UUID.fromString(decoder.decodeString())
    }
}

class HttpAgentEngineClient(
    private val serverUrl: String
) : AgentEngineClient {

    private val httpClient: HttpClient = HttpClient.newBuilder()
        /*
            Force HTTP/1.1: Java HttpClient may try an h2c (HTTP/2 cleartext) upgrade
            via `Upgrade: h2c` / `HTTP2-Settings`, which our server rejects as an invalid request.
         */
        .version(HttpClient.Version.HTTP_1_1)
        .connectTimeout(Duration.ofSeconds(30))
        .build()

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        serializersModule = SerializersModule {
            contextual(UUIDSerializer)
        }
    }

    private lateinit var currentSessionId: UUID

    override suspend fun newSession(
        agentSettings: ClientAgentSettings,
        projectPath: String,
        initialHistory: List<Message>,
    ): SessionInfo {
        val requestBody = NewSessionRequestDto(
            agentSettings = agentSettings,
            projectPath = projectPath,
            initialHistory = initialHistory.map { it.toDto() }
        )

        val response = post<NewSessionResponseDto, NewSessionRequestDto>("/newSession", requestBody)

        currentSessionId = response.id
        return SessionInfo(
            id = response.id,
            state = response.state,
            lastMessageId = response.lastMessageId,
            timeout = response.timeout,
            error = response.error,
            errorTimestamp = response.errorTimestamp,
            lastTurnCostUsd = response.costUsd,
        )
    }

    override suspend fun getSessionInfo(id: UUID): SessionInfo {
        val requestBody = GetSessionInfoRequestDto(id = id)
        val response = post<SessionInfoDto, GetSessionInfoRequestDto>("/getSessionInfo", requestBody)

        return SessionInfo(
            id = response.id,
            state = response.state,
            lastMessageId = response.lastMessageId,
            timeout = response.timeout,
            error = response.error,
            errorTimestamp = response.errorTimestamp,
            lastTurnCostUsd = response.lastTurnCostUsd,
        )
    }


    override suspend fun getMessages(fromExcl: UUID?, toIncl: UUID?): List<Message> {
        val requestBody = GetMessagesRequestDto(
            sessionId = currentSessionId,
            fromExcl = fromExcl,
            toIncl = toIncl
        )

        val response = post<List<MessageDto>, GetMessagesRequestDto>("/getMessages", requestBody)
        return response.map { it.toDomain() }
    }

    override suspend fun submitUserMessage(content: String, timeoutMillis: Long?) {
        val requestBody = SubmitUserMessageRequestDto(
            sessionId = currentSessionId,
            content = content,
            timeoutMillis = timeoutMillis
        )

        post<SubmitUserMessageResponseDto, SubmitUserMessageRequestDto>("/submitUserMessage", requestBody)
    }

    override suspend fun getRawChatDump(id: UUID): String {
        val requestBody = GetChatDumpRequestDto(sessionId = id)
        return postRaw("/getChatDump", requestBody)
    }

    private suspend inline fun <reified T, reified R> post(endpoint: String, body: R): T =
        json.decodeFromString(serializer<T>(), postRaw(endpoint, body))

    private suspend inline fun <reified R> postRaw(endpoint: String, body: R): String {
        val requestBodyJson = json.encodeToString(serializer<R>(), body)
        val request = HttpRequest.newBuilder()
            .uri(URI.create("$serverUrl$endpoint"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(requestBodyJson))
            .build()
        val response = httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString()).await()
        if (response.statusCode() !in 200..299) {
            error("HTTP request failed with status ${response.statusCode()}: ${response.body()}")
        }
        return response.body()
    }

    @Serializable
    private data class NewSessionRequestDto(
        val agentSettings: ClientAgentSettings,
        val projectPath: String,
        val initialHistory: List<MessageDto>
    )

    @Serializable
    private data class NewSessionResponseDto(
        @Serializable(with = UUIDSerializer::class)
        val id: UUID,
        val state: SessionState,
        @Serializable(with = UUIDSerializer::class)
        val lastMessageId: UUID?,
        val timeout: Boolean,
        val error: String? = null,
        val errorTimestamp: Long? = null,
        val costUsd: Float? = null,
    )

    @Serializable
    private data class GetSessionInfoRequestDto(
        @Serializable(with = UUIDSerializer::class)
        val id: UUID
    )

    @Serializable
    private data class SessionInfoDto(
        @Serializable(with = UUIDSerializer::class)
        val id: UUID,
        val state: SessionState,
        @Serializable(with = UUIDSerializer::class)
        val lastMessageId: UUID?,
        val timeout: Boolean,
        val error: String? = null,
        val errorTimestamp: Long? = null,
        val lastTurnCostUsd: Float? = null,
    )

    @Serializable
    private data class GetMessagesRequestDto(
        @Serializable(with = UUIDSerializer::class)
        val sessionId: UUID,
        @Serializable(with = UUIDSerializer::class)
        val fromExcl: UUID?,
        @Serializable(with = UUIDSerializer::class)
        val toIncl: UUID?
    )

    @Serializable
    private data class MessageDto(
        @Serializable(with = UUIDSerializer::class)
        val id: UUID,
        val timestamp: Long?,
        val kind: MessageKind,
        val content: String,
        val reasoning: String?,
        val toolCalls: List<ToolCallDto>,
        val toolResponses: List<ToolResponseDto>
    ) {
        fun toDomain() = Message(
            id,
            timestamp,
            kind,
            content,
            reasoning,
            toolCalls.map { it.toDomain() },
            toolResponses.map { it.toDomain() })
    }

    @Serializable
    private data class ToolCallDto(
        val id: String,
        val name: String,
        val args: String
    ) {
        fun toDomain() = ToolCall(id, name, args)
    }

    @Serializable
    private data class ToolResponseDto(
        val id: String,
        val name: String,
        val content: String,
        // Default keeps compatibility with adapters that do not yet emit this field.
        val success: Boolean = true,
    ) {
        fun toDomain() = ToolResponse(id, name, content, success)
    }

    @Serializable
    private data class SubmitUserMessageRequestDto(
        @Serializable(with = UUIDSerializer::class)
        val sessionId: UUID,
        val content: String,
        val timeoutMillis: Long?
    )

    @Serializable
    private data class SubmitUserMessageResponseDto(val sessionInfo: SessionInfoDto)

    @Serializable
    private data class GetChatDumpRequestDto(
        @Serializable(with = UUIDSerializer::class)
        val sessionId: UUID
    )

    private fun Message.toDto() = MessageDto(
        id,
        timestamp,
        type,
        text,
        reasoning,
        toolCalls.map { it.toDto() },
        toolResponses.map { it.toDto() })

    private fun ToolCall.toDto() = ToolCallDto(id, name, arguments)

    private fun ToolResponse.toDto() = ToolResponseDto(id, name, responseData, success)
}
