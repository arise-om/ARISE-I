package tech.ironlabs.arisei.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Same fixture as tests/test_golden.py: a live run over these names must
 * leave every file exactly where the Python engine leaves it.
 */
class ClassifierParityTest {
    private val fixture: JsonObject = Json.parseToJsonElement(
        File(System.getProperty("arise.golden")).readText(),
    ).jsonObject

    @Test
    fun `android engine matches the python golden fixture`() {
        val box = Sandbox()
        val preexisting = fixture["preexisting"]!!.jsonArray.map { it.jsonPrimitive.content }
        preexisting.forEach { box.file(it, "old") }
        val cases = fixture["cases"]!!.jsonArray.map { it.jsonObject }
        cases.forEach { box.file(it["name"]!!.jsonPrimitive.content, "x") }

        val organizer = box.organizer()
        organizer.execute(organizer.plan(box.root))

        val actual = box.tree().keys - preexisting.toSet()
        val expected = cases.map { it["expect"]!!.jsonPrimitive.content }.toSet()
        assertEquals(expected.sorted(), actual.sorted())
    }
}
