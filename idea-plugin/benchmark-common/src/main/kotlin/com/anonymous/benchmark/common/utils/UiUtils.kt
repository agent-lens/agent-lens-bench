package com.anonymous.benchmark.common.utils

import com.anonymous.benchmark.common.bundle.BenchmarkBundle
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationListener
import com.intellij.notification.NotificationType
import com.intellij.openapi.Disposable
import com.intellij.openapi.observable.properties.ObservableProperty
import com.intellij.openapi.project.Project
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch


fun <T> ObservableProperty<T>.afterNonEqChange(
    parentDisposable: Disposable? = null,
    listener: (T) -> Unit,
) {
    var lastSeenValue = get()
    afterChange(parentDisposable) { newValue ->
        val oldValue = lastSeenValue
        lastSeenValue = newValue
        if (oldValue != newValue) {
            listener(newValue)
        }
    }
}

fun Project.showNotificationToUser(
    scope: CoroutineScope,
    message: String,
    type: NotificationType,
) {
    scope.launch(Dispatchers.Main) {
        val notificationGroup = NotificationGroupManager.getInstance()
            .getNotificationGroup(BenchmarkBundle.message("notification.group.benchmark.notifications"))

        notificationGroup
            .createNotification(message, type)
            .apply {
                setListener(NotificationListener.URL_OPENING_LISTENER)
            }
            .notify(this@showNotificationToUser)
    }
}
