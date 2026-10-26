package tech.ironlabs.arisei

import android.app.Application
import tech.ironlabs.arisei.data.AriseRepository
import tech.ironlabs.arisei.data.SettingsRepository
import tech.ironlabs.arisei.platform.Notifier
import tech.ironlabs.arisei.platform.Scheduler

class AriseApp : Application() {
    lateinit var repository: AriseRepository
        private set

    override fun onCreate() {
        super.onCreate()
        repository = AriseRepository(this, SettingsRepository(this))
        Notifier.createChannels(this)
        Scheduler.sync(this, repository.settings.value)
    }
}

val android.content.Context.repository: AriseRepository
    get() = (applicationContext as AriseApp).repository
