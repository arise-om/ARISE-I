package tech.ironlabs.arisei

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import tech.ironlabs.arisei.platform.Notifier
import tech.ironlabs.arisei.ui.AriseRoot
import tech.ironlabs.arisei.ui.AriseViewModel
import tech.ironlabs.arisei.ui.Tab
import tech.ironlabs.arisei.ui.theme.AriseTheme

class MainActivity : ComponentActivity() {
    private val vm: AriseViewModel by viewModels()
    private var requestedTab by mutableStateOf<Tab?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        requestedTab = tabFrom(intent)
        setContent {
            val settings by repository.settings.settings.collectAsStateWithLifecycle()
            AriseTheme(settings.theme, settings.dynamicColor, settings.reduceMotion) {
                AriseRoot(vm, requestedTab, onTabConsumed = { requestedTab = null })
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        requestedTab = tabFrom(intent)
    }

    private fun tabFrom(intent: Intent?): Tab? =
        if (intent?.getStringExtra(Notifier.EXTRA_TAB) == Notifier.TAB_REVIEW) Tab.REVIEW else null
}
