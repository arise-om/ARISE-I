package tech.ironlabs.arisei.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.automirrored.outlined.Undo
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import tech.ironlabs.arisei.R
import tech.ironlabs.arisei.platform.Permissions
import tech.ironlabs.arisei.ui.components.FolderPickerDialog
import tech.ironlabs.arisei.ui.theme.AriseTokens
import tech.ironlabs.arisei.ui.theme.LocalAriseColors
import tech.ironlabs.arisei.ui.theme.LocalReduceMotion
import java.io.File

/** Three steps — welcome, access, folder — ending straight in the Plan. */
@Composable
fun OnboardingScreen(
    hasAccess: Boolean,
    defaultFolder: File,
    onRequestAccess: () -> Unit,
    onFinish: (File) -> Unit,
    onSkip: () -> Unit,
) {
    var step by rememberSaveable { mutableIntStateOf(0) }
    val reduce = LocalReduceMotion.current
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface).safeDrawingPadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            StepDots(step, Modifier.padding(start = 16.dp).weight(1f))
            TextButton(onClick = onSkip) { Text(stringResource(R.string.action_skip)) }
        }
        AnimatedContent(
            targetState = step,
            transitionSpec = {
                val d = if (reduce) 0 else AriseTokens.Motion.SCREEN
                fadeIn(tween(d)) togetherWith fadeOut(tween(d))
            },
            label = "onboarding",
            modifier = Modifier.weight(1f),
        ) { s ->
            when (s) {
                0 -> WelcomeStep(onNext = { step = if (hasAccess) 2 else 1 })
                1 -> AccessStep(hasAccess, onRequestAccess, onNext = { step = 2 })
                else -> FolderStep(defaultFolder, onFinish)
            }
        }
    }
}

@Composable
private fun StepDots(step: Int, modifier: Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        repeat(3) { i ->
            Box(
                Modifier.height(6.dp).width(if (i == step) 20.dp else 6.dp).clip(CircleShape)
                    .background(if (i <= step) LocalAriseColors.current.brandAccent else MaterialTheme.colorScheme.outlineVariant),
            )
        }
    }
}

@Composable
private fun StepScaffold(
    icon: ImageVector,
    title: String,
    body: String,
    primary: String,
    primaryEnabled: Boolean = true,
    onPrimary: () -> Unit,
    content: @Composable () -> Unit = {},
) {
    Column(Modifier.fillMaxSize().padding(horizontal = 24.dp)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(32.dp))
            Box(
                Modifier.size(64.dp).clip(CircleShape).background(LocalAriseColors.current.brandAccent),
                contentAlignment = Alignment.Center,
            ) { Icon(icon, null, tint = androidx.compose.ui.graphics.Color.White, modifier = Modifier.size(32.dp)) }
            Spacer(Modifier.height(24.dp))
            Text(
                title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(Modifier.height(12.dp))
            Text(body, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(24.dp))
            content()
        }
        Button(
            onClick = onPrimary, enabled = primaryEnabled,
            modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp).height(52.dp),
        ) { Text(primary) }
    }
}

@Composable
private fun WelcomeStep(onNext: () -> Unit) {
    StepScaffold(
        icon = Icons.Outlined.AutoAwesome,
        title = stringResource(R.string.onb_welcome_title),
        body = stringResource(R.string.onb_welcome_body),
        primary = stringResource(R.string.action_continue),
        onPrimary = onNext,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Feature(Icons.Outlined.AutoAwesome, stringResource(R.string.onb_feature_ai))
            Feature(Icons.Outlined.Inbox, stringResource(R.string.onb_feature_review))
            Feature(Icons.AutoMirrored.Outlined.Undo, stringResource(R.string.onb_feature_undo))
            Feature(Icons.Outlined.Lock, stringResource(R.string.onb_feature_local))
        }
    }
}

@Composable
private fun Feature(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(14.dp))
        Text(text, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun AccessStep(hasAccess: Boolean, onRequestAccess: () -> Unit, onNext: () -> Unit) {
    StepScaffold(
        icon = Icons.Outlined.Lock,
        title = stringResource(R.string.onb_access_title),
        body = stringResource(R.string.onb_access_body),
        primary = stringResource(if (hasAccess) R.string.action_continue else R.string.action_open_settings),
        onPrimary = if (hasAccess) onNext else onRequestAccess,
    ) {
        if (hasAccess) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.CheckCircle, null, tint = LocalAriseColors.current.success)
                Spacer(Modifier.width(10.dp))
                Text(stringResource(R.string.onb_access_granted), style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable
private fun FolderStep(defaultFolder: File, onFinish: (File) -> Unit) {
    var chosen by remember { mutableStateOf(defaultFolder) }
    var picking by remember { mutableStateOf(false) }
    val options = remember(chosen) { listOf(defaultFolder, chosen).distinct() }
    StepScaffold(
        icon = Icons.Outlined.Folder,
        title = stringResource(R.string.onb_folder_title),
        body = stringResource(R.string.onb_folder_body),
        primary = stringResource(R.string.onb_lets_go),
        onPrimary = { onFinish(chosen) },
    ) {
        options.forEach { dir ->
            val loose = remember(dir) { dir.listFiles()?.count { it.isFile && !it.name.startsWith(".") } ?: 0 }
            Row(
                Modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).clickable { chosen = dir }.padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = chosen == dir, onClick = { chosen = dir })
                Column(Modifier.weight(1f)) {
                    Text(dir.name, style = MaterialTheme.typography.titleMedium)
                    Text(
                        LocalContext.current.resources.getQuantityString(R.plurals.folder_hint_loose, loose, loose),
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        TextButton(onClick = { picking = true }) { Text(stringResource(R.string.folder_add)) }
    }
    if (picking) FolderPickerDialog(onDismiss = { picking = false }, onPick = { chosen = it; picking = false })
}

/** Launcher for the storage permission: settings screen on API 30+, runtime dialog below. */
@Composable
fun rememberAccessRequester(onResult: () -> Unit): () -> Unit {
    val context = LocalContext.current
    val legacy = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { onResult() }
    val settings = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { onResult() }
    return {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            settings.launch(Permissions.allFilesAccessIntent(context))
        } else {
            legacy.launch(Permissions.legacyStoragePermissions)
        }
    }
}
