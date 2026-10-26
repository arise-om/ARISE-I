package tech.ironlabs.arisei

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.merge
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import tech.ironlabs.arisei.data.AriseRepository
import tech.ironlabs.arisei.data.SettingsRepository
import tech.ironlabs.arisei.platform.Notifier
import tech.ironlabs.arisei.platform.OrganizeWidget
import tech.ironlabs.arisei.platform.Scheduler

class AriseApp : Application() {
    lateinit var repository: AriseRepository
        private set

    override fun onCreate() {
        super.onCreate()
        repository = AriseRepository(this, SettingsRepository(this))
        Notifier.createChannels(this)
        Scheduler.sync(this, repository.settings.value)
        // Keep the home-screen widget's loose-file count current.
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            merge(repository.changed, repository.settings.settings.map { }).collect {
                runCatching { OrganizeWidget.refresh(this@AriseApp) }
            }
        }
    }
}

val android.content.Context.repository: AriseRepository
    get() = (applicationContext as AriseApp).repository
