/* Isolated sel4test collision probe. Append to frames.c inside disposable CI checkout. */
static int test_pagemap_collision_isolated(env_t env)
{
    seL4_CPtr frame_a = vka_alloc_frame_leaky(&env->vka, seL4_PageBits);
    seL4_CPtr frame_b = vka_alloc_frame_leaky(&env->vka, seL4_PageBits);
    test_assert(frame_a && frame_b);

    void *va = NULL;
    reservation_t reserved = vspace_reserve_range_aligned(
        &env->vspace, BIT(seL4_PageBits), seL4_PageBits,
        seL4_AllRights, 1, &va);
    test_assert(reserved.res && va != NULL);

    uintptr_t cookie = 0;
    int map_a = vspace_map_pages_at_vaddr(
        &env->vspace, &frame_a, &cookie, va, 1, seL4_PageBits, reserved);
    printf("PAGEMAP_RESULT map_a=%d\\n", map_a);
    test_error_eq(map_a, seL4_NoError);
    if (map_a != seL4_NoError) {
        return sel4test_get_result();
    }

    volatile seL4_Word *word = (volatile seL4_Word *)va;
    const seL4_Word marker = (seL4_Word)0x5a3c1d7b;
    *word = marker;

    /* Seed frame B at another temporary address, then unmap it. */
    uintptr_t cookie_b = 0;
    void *temp_b = vspace_map_pages(
        &env->vspace, &frame_b, &cookie_b,
        seL4_AllRights, 1, seL4_PageBits, 1);
    test_assert(temp_b != NULL);
    if (!temp_b) {
        return sel4test_get_result();
    }
    *(volatile seL4_Word *)temp_b = (seL4_Word)0x6b4d2e8c;
    vspace_unmap_pages(&env->vspace, temp_b, 1, seL4_PageBits, VSPACE_PRESERVE);

    int map_b = seL4_ARCH_Page_Map(
        frame_b, env->page_directory, (seL4_Word)va,
        seL4_AllRights, seL4_ARCH_Default_VMAttributes);
    printf("PAGEMAP_RESULT map_b_occupied=%d expected_delete_first=%d\\n",
           map_b, seL4_DeleteFirst);

    if (map_b == seL4_NoError) {
        seL4_Word actual = *word;
        printf("PAGEMAP_RESULT collision_read=0x%lx expected_a=0x%lx expected_b=0x%lx\\n",
               (unsigned long)actual, (unsigned long)marker, (unsigned long)0x6b4d2e8c);
        /* Stale-cap consequence: A's old cap still records this VA. Check
         * whether invoking Page_Map on A reclaims it, then restore B.
         * This stays inside the same VSpace and uses owned frames only. */
        int remap_stale_a = seL4_ARCH_Page_Map(
            frame_a, env->page_directory, (seL4_Word)va,
            seL4_AllRights, seL4_ARCH_Default_VMAttributes);
        printf("PAGEMAP_RESULT stale_a_map_same_va=%d\\n", remap_stale_a);
        if (remap_stale_a == seL4_NoError) {
            printf("PAGEMAP_RESULT stale_a_map_read=0x%lx\\n",
                   (unsigned long)*word);
            int restore_b = seL4_ARCH_Page_Map(
                frame_b, env->page_directory, (seL4_Word)va,
                seL4_AllRights, seL4_ARCH_Default_VMAttributes);
            printf("PAGEMAP_RESULT restore_b_after_stale_a=%d\\n", restore_b);
            if (restore_b == seL4_NoError) {
                printf("PAGEMAP_RESULT restored_b_read=0x%lx\\n",
                       (unsigned long)*word);
            }
        }

        /* An obsolete Frame A cap must not be able to change Frame B's mapping.
         * Keep all follow-up accesses guarded by successful Page_Map calls.
         * A direct post-unmap VA read is intentionally omitted: a failed
         * mapping would otherwise cause an unhandled VM fault. */
        int unmap_a = seL4_ARCH_Page_Unmap(frame_a);
        printf("PAGEMAP_RESULT unmap_a=%d\\n", unmap_a);

        /* If A's metadata was cleared, it must be reusable elsewhere. */
        void *a_elsewhere = NULL;
        reservation_t reserve_a = vspace_reserve_range_aligned(
            &env->vspace, BIT(seL4_PageBits), seL4_PageBits,
            seL4_AllRights, 1, &a_elsewhere);
        test_assert(reserve_a.res && a_elsewhere != NULL);
        if (reserve_a.res && a_elsewhere != NULL) {
            int remap_a_elsewhere = seL4_ARCH_Page_Map(
                frame_a, env->page_directory, (seL4_Word)a_elsewhere,
                seL4_AllRights, seL4_ARCH_Default_VMAttributes);
            printf("PAGEMAP_RESULT remap_a_elsewhere=%d\\n", remap_a_elsewhere);
            if (remap_a_elsewhere == seL4_NoError) {
                seL4_Word a_read = *(volatile seL4_Word *)a_elsewhere;
                printf("PAGEMAP_RESULT remap_a_content=0x%lx\\n",
                       (unsigned long)a_read);
                int unmap_a_elsewhere = seL4_ARCH_Page_Unmap(frame_a);
                printf("PAGEMAP_RESULT unmap_a_elsewhere=%d\\n", unmap_a_elsewhere);
            }
        }

        /* B must still allow a same-VA attribute update: the mapping-cap
         * relationship should remain coherent until B's own unmap. */
        int remap_b_same = seL4_ARCH_Page_Map(
            frame_b, env->page_directory, (seL4_Word)va,
            seL4_AllRights, seL4_ARCH_Default_VMAttributes);
        printf("PAGEMAP_RESULT remap_b_same_va=%d\\n", remap_b_same);
        if (remap_b_same == seL4_NoError) {
            printf("PAGEMAP_RESULT b_after_stale_a_unmap=0x%lx\\n",
                   (unsigned long)*word);
        }

        int unmap_b = seL4_ARCH_Page_Unmap(frame_b);
        printf("PAGEMAP_RESULT unmap_b=%d\\n", unmap_b);
        /* An explicitly unmapped B should leave the VA available. */
        int remap_a_original = seL4_ARCH_Page_Map(
            frame_a, env->page_directory, (seL4_Word)va,
            seL4_AllRights, seL4_ARCH_Default_VMAttributes);
        printf("PAGEMAP_RESULT remap_a_original=%d\\n", remap_a_original);
        if (remap_a_original == seL4_NoError) {
            printf("PAGEMAP_RESULT a_after_b_unmap=0x%lx\\n",
                   (unsigned long)*word);
            seL4_ARCH_Page_Unmap(frame_a);
        }
    } else {
        printf("PAGEMAP_RESULT rejected_without_further_unmap_probe=1\\n");
    }
    return sel4test_get_result();
}
DEFINE_TEST(PAGEMAP0001, "Isolated occupied Page_Map collision probe",
            test_pagemap_collision_isolated, true)
