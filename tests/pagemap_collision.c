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
        int unmap_a = seL4_ARCH_Page_Unmap(frame_a);
        printf("PAGEMAP_RESULT unmap_a=%d\\n", unmap_a);
        int unmap_b = seL4_ARCH_Page_Unmap(frame_b);
        printf("PAGEMAP_RESULT unmap_b=%d\\n", unmap_b);
        /* Never dereference VA after unmapping: avoid inducing a VM fault. */
    } else {
        printf("PAGEMAP_RESULT rejected_without_further_unmap_probe=1\\n");
    }
    return sel4test_get_result();
}
DEFINE_TEST(PAGEMAP0001, "Isolated occupied Page_Map collision probe",
            test_pagemap_collision_isolated, true)
